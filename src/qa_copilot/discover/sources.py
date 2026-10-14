from __future__ import annotations

import html
import os
import re
from typing import Any, Callable
from urllib.parse import urlencode

from qa_copilot.httputil import USER_AGENT, get_json
from qa_copilot.models import Listing, utc_now
from qa_copilot.policy import PolicyError
from qa_copilot.redact import redact

from .ids import listing_id

Fetcher = Callable[[int], list[Listing]]

# Used by the high-volume aggregators to keep only QA-shaped rows, in English and
# Japanese. Deliberately broader than qualify(): discovery is cheap, noise is not.
_QA_RE = re.compile(
    r"\b(qa|q\.a\.|quality|test|testing|tester|sdet|automation|playwright|cypress|"
    r"selenium|e2e|regression|a11y|accessibility|bug|defect|repro|flaky|flake|crash)\b"
    r"|(テスト|品質|検証|不具合|バグ)",
    re.I,
)


def _is_qa_like(text: str) -> bool:
    return bool(_QA_RE.search(text or ""))


def _github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_search(source_id: str, query: str, limit: int) -> list[dict]:
    """Run one GitHub Search API query.

    NOTE: GitHub rejects ``OR`` between *qualifiers*
    ("logical operators only apply to text, not to qualifiers"), so every query
    here must AND its qualifiers and never join labels with OR. Do not "simplify"
    the callers back into a single OR-ed query.
    """
    params = urlencode(
        {
            "q": query,
            "per_page": min(max(limit, 1), 100),
            "sort": "created",
            "order": "desc",
        }
    )
    data = get_json(source_id, f"https://api.github.com/search/issues?{params}", headers=_github_headers())
    if not isinstance(data, dict):
        raise PolicyError(f"{source_id}: unexpected payload")
    return [item for item in (data.get("items") or []) if isinstance(item, dict)]


# Hacker News hiring comments are free prose, so a loose keyword match returns
# "Growth Marketing Manager" because the body says "test". The first line is the
# role header, so match QA role titles there instead.
_QA_ROLE_RE = re.compile(
    r"\b(qa|q\.?a\.?|sdet|software\s+tester|"
    r"test\s+(?:engineer|engineering|lead|manager|analyst|automation|specialist|architect|developer)|"
    r"(?:test|qa)\s+automation|"
    r"quality\s+(?:assurance|engineer|engineering|lead|analyst|manager))\b",
    re.I,
)


def _looks_like_qa_role(comment: str) -> bool:
    header = (comment or "").strip().split("\n", 1)[0]
    return bool(_QA_ROLE_RE.search(header))


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", " ", text)).strip()



def _s(obj: Any, *keys: str, default: str = "") -> str:
    if not isinstance(obj, dict):
        return default
    for key in keys:
        val = obj.get(key)
        if val is None:
            continue
        if isinstance(val, list):
            return " ".join(str(x) for x in val)
        return str(val)
    return default


def _tags(obj: Any, *keys: str) -> list[str]:
    if not isinstance(obj, dict):
        return []
    for key in keys:
        val = obj.get(key)
        if isinstance(val, list):
            return [str(x) for x in val if x]
        if isinstance(val, str) and val:
            return [p.strip() for p in re.split(r"[,|]", val) if p.strip()]
    return []


def _listing_from_github(source: str, item: dict) -> Listing:
    html = _s(item, "html_url")
    return Listing(
        id=listing_id(source, html),
        source=source,
        title=_s(item, "title"),
        url=html,
        company=_s(item, "repository_url").rsplit("/", 2)[-2] if _s(item, "repository_url") else "",
        description=redact(_s(item, "body")[:4000]),
        tags=[_s(lb, "name") for lb in (item.get("labels") or []) if isinstance(lb, dict)],
        fetched_at=utc_now(),
        extra={
            "repo_url": _s(item, "repository_url"),
            "number": item.get("number"),
            # An assignee usually means the bounty is already claimed. Chasing a
            # claimed bounty is the fastest way to earn nothing.
            "assignees": [
                _s(a, "login") for a in (item.get("assignees") or []) if isinstance(a, dict)
            ],
        },
    )


def fetch_github_issues(limit: int = 20) -> list[Listing]:
    # One qualifier-only query, then filter locally. `(a OR b) label:x` is a 422.
    items = _github_search("github_issues", 'is:issue is:open label:"good first issue"', limit * 4)
    out: list[Listing] = []
    for item in items:
        labels = " ".join(_s(lb, "name") for lb in (item.get("labels") or []) if isinstance(lb, dict))
        if not _is_qa_like(f"{_s(item, 'title')} {labels} {_s(item, 'body')}"):
            continue
        out.append(_listing_from_github("github_issues", item))
        if len(out) >= limit:
            break
    return out


# Algora and friends label bounties with an emoji, so we search label-by-label
# instead of OR-ing them (GitHub rejects OR between qualifiers).
BOUNTY_LABELS = ("bounty", "💎 Bounty")


def fetch_github_bounties(limit: int = 20) -> list[Listing]:
    out: list[Listing] = []
    seen: set[str] = set()
    for label in BOUNTY_LABELS:
        if len(out) >= limit:
            break
        items = _github_search("github_bounties", f'is:issue is:open label:"{label}"', 100)
        for item in items:
            url = _s(item, "html_url")
            if not url or url in seen:
                continue
            labels = " ".join(_s(lb, "name") for lb in (item.get("labels") or []) if isinstance(lb, dict))
            if not _is_qa_like(f"{_s(item, 'title')} {labels} {_s(item, 'body')}"):
                continue
            seen.add(url)
            listing = _listing_from_github("github_bounties", item)
            listing.tags = list(dict.fromkeys(listing.tags + ["bounty"]))
            out.append(listing)
            if len(out) >= limit:
                break
    return out


def fetch_remotive(limit: int = 20) -> list[Listing]:
    data = get_json("remotive", "https://remotive.com/api/remote-jobs?search=qa%20test&limit=50")
    jobs = data.get("jobs") if isinstance(data, dict) else []
    out: list[Listing] = []
    for job in jobs or []:
        url = _s(job, "url")
        out.append(
            Listing(
                id=listing_id("remotive", url),
                source="remotive",
                title=_s(job, "title"),
                url=url,
                company=_s(job, "company_name"),
                description=redact(_s(job, "description")[:4000]),
                tags=_tags(job, "tags") + ([_s(job, "category")] if _s(job, "category") else []),
                fetched_at=utc_now(),
                attribution="Source: Remotive (https://remotive.com). Apply on the original listing.",
            )
        )
        if len(out) >= limit:
            break
    return out


def fetch_remoteok(limit: int = 20) -> list[Listing]:
    data = get_json("remoteok", "https://remoteok.com/api")
    if not isinstance(data, list):
        raise PolicyError("remoteok: expected a JSON list")
    out: list[Listing] = []
    for job in data:
        if not isinstance(job, dict) or not job.get("position"):
            continue
        url = _s(job, "url", "apply_url")
        tags = _tags(job, "tags")
        blob = f"{job.get('position','')} {' '.join(tags)}".lower()
        if not re.search(r"qa|test|quality|sdet|automation", blob):
            continue
        out.append(
            Listing(
                id=listing_id("remoteok", url or _s(job, "id")),
                source="remoteok",
                title=_s(job, "position"),
                url=url,
                company=_s(job, "company"),
                description=redact(_s(job, "description")[:4000]),
                tags=tags,
                fetched_at=utc_now(),
                attribution="Source: Remote OK. Link back to the original Remote OK URL.",
            )
        )
        if len(out) >= limit:
            break
    return out


def fetch_jobicy(limit: int = 20) -> list[Listing]:
    data = get_json("jobicy", "https://jobicy.com/api/v2/remote-jobs?count=50&tag=qa")
    jobs = data.get("jobs") if isinstance(data, dict) else []
    out: list[Listing] = []
    for job in jobs or []:
        url = _s(job, "url", "jobSlug")
        title = _s(job, "jobTitle", "title")
        out.append(
            Listing(
                id=listing_id("jobicy", url or title),
                source="jobicy",
                title=title,
                url=url,
                company=_s(job, "companyName", "company"),
                description=redact(_s(job, "jobDescription", "jobExcerpt", "description")[:4000]),
                tags=_tags(job, "jobTags", "tags"),
                fetched_at=utc_now(),
                attribution="Source: Jobicy. Apply on the original listing.",
            )
        )
        if len(out) >= limit:
            break
    return out


def fetch_himalayas(limit: int = 20) -> list[Listing]:
    data = get_json("himalayas", "https://himalayas.app/jobs/api?limit=50")
    jobs = data.get("jobs") if isinstance(data, dict) else []
    out: list[Listing] = []
    for job in jobs or []:
        title = _s(job, "title", "jobTitle")
        if not re.search(r"qa|test|quality|sdet", title, re.I):
            continue
        url = _s(job, "applicationUrl", "url", "guid")
        out.append(
            Listing(
                id=listing_id("himalayas", url or title),
                source="himalayas",
                title=title,
                url=url,
                company=_s(job, "companyName", "company"),
                description=redact(_s(job, "description", "excerpt")[:4000]),
                tags=_tags(job, "categories", "tags"),
                fetched_at=utc_now(),
                attribution="Source: Himalayas. Apply on the original listing.",
            )
        )
        if len(out) >= limit:
            break
    return out


def fetch_working_nomads(limit: int = 20) -> list[Listing]:
    data = get_json("working_nomads", "https://www.workingnomads.com/api/exposed_jobs/")
    if not isinstance(data, list):
        raise PolicyError("working_nomads: expected a JSON list")
    out: list[Listing] = []
    for job in data:
        title = _s(job, "title")
        tags = _tags(job, "tags", "category")
        blob = f"{title} {' '.join(tags)} {_s(job, 'category')}".lower()
        if not re.search(r"qa|test|quality|sdet", blob):
            continue
        url = _s(job, "url")
        out.append(
            Listing(
                id=listing_id("working_nomads", url or title),
                source="working_nomads",
                title=title,
                url=url,
                company=_s(job, "company_name", "company"),
                description=redact(_s(job, "description")[:4000]),
                tags=tags,
                fetched_at=utc_now(),
                attribution="Source: Working Nomads. Apply on the original listing.",
            )
        )
        if len(out) >= limit:
            break
    return out


def fetch_arbeitnow(limit: int = 20) -> list[Listing]:
    data = get_json("arbeitnow", "https://www.arbeitnow.com/api/job-board-api")
    rows = data.get("data") if isinstance(data, dict) else None
    out: list[Listing] = []
    seen: set[tuple[str, str]] = set()
    for job in rows or []:
        if not isinstance(job, dict):
            continue
        title = _s(job, "title")
        tags = _tags(job, "tags") + _tags(job, "job_types")
        location = _s(job, "location")
        if not _is_qa_like(f"{title} {' '.join(tags)} {location}"):
            continue
        # The same role is often posted once per city; keep only the first.
        dedupe_key = (title.strip().lower(), _s(job, "company_name").strip().lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        url = _s(job, "url")
        out.append(
            Listing(
                id=listing_id("arbeitnow", url or _s(job, "slug")),
                source="arbeitnow",
                title=title,
                url=url,
                company=_s(job, "company_name"),
                description=redact(_strip_html(_s(job, "description"))[:4000]),
                tags=tags,
                fetched_at=utc_now(),
                attribution="Source: Arbeitnow (https://www.arbeitnow.com). Apply on the original listing.",
                extra={"location": location, "remote": job.get("remote")},
            )
        )
        if len(out) >= limit:
            break
    return out


def fetch_fourdayweek(limit: int = 20) -> list[Listing]:
    data = get_json("fourdayweek", "https://4dayweek.io/api/jobs")
    jobs = data.get("jobs") if isinstance(data, dict) else None
    out: list[Listing] = []
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        title = _s(job, "title")
        category = _s(job, "category")
        if not _is_qa_like(f"{title} {category}"):
            continue
        slug = _s(job, "slug")
        url = f"https://4dayweek.io/job/{slug}" if slug else f"https://4dayweek.io/job/{_s(job, 'id')}"
        locations = [
            loc.get("city") or loc.get("country")
            for loc in (job.get("locations") or [])
            if isinstance(loc, dict)
        ]
        out.append(
            Listing(
                id=listing_id("fourdayweek", url),
                source="fourdayweek",
                title=title,
                url=url,
                company=_s(job, "company_name"),
                description=redact(f"{category} / {_s(job, 'schedule_type')} / {_s(job, 'level')}"),
                tags=[t for t in (category, _s(job, "schedule_type")) if t],
                fetched_at=utc_now(),
                attribution="Source: 4dayweek.io. Apply on the original listing.",
                extra={"locations": ", ".join(l for l in locations if l), "schedule_type": _s(job, "schedule_type")},
            )
        )
        if len(out) >= limit:
            break
    return out


def fetch_careerjet(limit: int = 20) -> list[Listing]:
    affid = os.environ.get("CAREERJET_AFFID", "0")
    referer = os.environ.get("CAREERJET_REFERER", "https://github.com/RyoSAKu610/qa-copilot")
    locales = [l.strip() for l in os.environ.get("CAREERJET_LOCALES", "ja_JP,en_GB").split(",") if l.strip()]
    out: list[Listing] = []
    seen: set[str] = set()
    for locale in locales:
        if len(out) >= limit:
            break
        keywords = "QA テスト" if locale.lower().startswith("ja") else "QA automation test"
        params = urlencode(
            {
                "keywords": keywords,
                "location": "",
                "affid": affid,
                "user_ip": os.environ.get("CAREERJET_USER_IP", "127.0.0.1"),
                "user_agent": USER_AGENT,
                "locale_code": locale,
                "pagesize": min(limit, 100),
            }
        )
        # Careerjet's public endpoint is http-only and requires a Referer.
        data = get_json("careerjet", f"http://public.api.careerjet.net/search?{params}", headers={"Referer": referer})
        jobs = data.get("jobs") if isinstance(data, dict) else None
        for job in jobs or []:
            if not isinstance(job, dict):
                continue
            url = _s(job, "url")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(
                Listing(
                    id=listing_id("careerjet", url),
                    source="careerjet",
                    title=_s(job, "title"),
                    url=url,
                    company=_s(job, "company"),
                    description=redact(_strip_html(_s(job, "description"))[:4000]),
                    tags=[locale],
                    fetched_at=utc_now(),
                    attribution=f"Source: Careerjet ({locale}). Apply on the original listing.",
                    extra={"locale": locale, "location": _s(job, "locations"), "salary": _s(job, "salary")},
                )
            )
            if len(out) >= limit:
                break
    return out


def fetch_adzuna(limit: int = 20) -> list[Listing]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise PolicyError("adzuna: set ADZUNA_APP_ID and ADZUNA_APP_KEY (free at developer.adzuna.com)")
    countries = [c.strip() for c in os.environ.get("ADZUNA_COUNTRIES", "jp,gb,us").split(",") if c.strip()]
    out: list[Listing] = []
    seen: set[str] = set()
    for country in countries:
        if len(out) >= limit:
            break
        params = urlencode(
            {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": min(limit, 50),
                "what": "QA test" if country != "jp" else "QA テスト",
                "content-type": "application/json",
            }
        )
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?{params}"
        data = get_json("adzuna", url)
        jobs = data.get("results") if isinstance(data, dict) else None
        for job in jobs or []:
            if not isinstance(job, dict):
                continue
            link = _s(job, "redirect_url")
            if not link or link in seen:
                continue
            seen.add(link)
            out.append(
                Listing(
                    id=listing_id("adzuna", link),
                    source="adzuna",
                    title=_s(job, "title"),
                    url=link,
                    company=_s(job.get("company"), "display_name"),
                    description=redact(_strip_html(_s(job, "description"))[:4000]),
                    tags=[country] + _tags(job, "category"),
                    fetched_at=utc_now(),
                    attribution=f"Source: Adzuna ({country}). Apply on the original listing.",
                    extra={"country": country, "location": _s(job.get("location"), "display_name")},
                )
            )
            if len(out) >= limit:
                break
    return out


def fetch_hn_hiring(limit: int = 20) -> list[Listing]:
    stories = get_json(
        "hn_hiring",
        "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=10&query=hiring",
    )
    hits = stories.get("hits") if isinstance(stories, dict) else None
    thread = next(
        (h for h in (hits or []) if isinstance(h, dict) and "Who is hiring" in _s(h, "title")),
        None,
    )
    if not thread:
        raise PolicyError("hn_hiring: could not locate the current 'Who is hiring' thread")
    thread_id = _s(thread, "objectID")
    # Pull every comment in the thread once, then filter locally by role title.
    # The Algolia full-text query alone is too loose (matches "test" in any
    # sentence) and too tight when combined with AND-style terms.
    comments = get_json(
        "hn_hiring",
        f"https://hn.algolia.com/api/v1/search?tags=comment,story_{thread_id}&hitsPerPage=1000",
    )
    rows = comments.get("hits") if isinstance(comments, dict) else None
    out: list[Listing] = []
    seen: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        text = _strip_html(_s(row, "comment_text"))
        if not _looks_like_qa_role(text):
            continue
        object_id = _s(row, "objectID")
        if object_id in seen:
            continue
        seen.add(object_id)
        url = f"https://news.ycombinator.com/item?id={object_id}"
        out.append(
            Listing(
                id=listing_id("hn_hiring", url),
                source="hn_hiring",
                title=text.split("\n", 1)[0][:120] or "HN: Who is hiring — QA role",
                url=url,
                company="",
                description=redact(text[:4000]),
                tags=["hn", "who-is-hiring"],
                fetched_at=utc_now(),
                attribution=f"Source: Hacker News '{_s(thread, 'title')}'. Reply by email or the linked form.",
                extra={"thread": f"https://news.ycombinator.com/item?id={thread_id}"},
            )
        )
        if len(out) >= limit:
            break
    return out


REGISTRY: dict[str, Fetcher] = {
    "github_issues": fetch_github_issues,
    "github_bounties": fetch_github_bounties,
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "jobicy": fetch_jobicy,
    "himalayas": fetch_himalayas,
    "working_nomads": fetch_working_nomads,
    "arbeitnow": fetch_arbeitnow,
    "fourdayweek": fetch_fourdayweek,
    "careerjet": fetch_careerjet,
    "adzuna": fetch_adzuna,
    "hn_hiring": fetch_hn_hiring,
}
