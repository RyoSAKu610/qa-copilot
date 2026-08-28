from __future__ import annotations

import os
import re
from typing import Any, Callable

from qa_copilot.httputil import get_json
from qa_copilot.models import Listing, utc_now
from qa_copilot.policy import PolicyError
from qa_copilot.redact import redact

from .ids import listing_id

Fetcher = Callable[[int], list[Listing]]

QA_QUERY = "qa OR test OR testing OR playwright OR a11y OR bug OR regression"


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


def fetch_github_issues(limit: int = 20) -> list[Listing]:
    q = f'is:issue is:open ({QA_QUERY}) label:"good first issue"'
    url = f"https://api.github.com/search/issues?q={q.replace(' ', '+')}&per_page={min(limit, 30)}"
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = get_json("github_issues", url, headers=headers)
    if not isinstance(data, dict):
        raise PolicyError("github_issues: unexpected payload")
    out: list[Listing] = []
    for item in data.get("items") or []:
        html = _s(item, "html_url")
        out.append(
            Listing(
                id=listing_id("github_issues", html),
                source="github_issues",
                title=_s(item, "title"),
                url=html,
                company=_s(item, "repository_url").rsplit("/", 2)[-2] if _s(item, "repository_url") else "",
                description=redact(_s(item, "body")[:4000]),
                tags=[
                    _s(lb, "name")
                    for lb in (item.get("labels") or [])
                    if isinstance(lb, dict)
                ],
                fetched_at=utc_now(),
                extra={"repo_url": _s(item, "repository_url"), "number": item.get("number")},
            )
        )
    return out[:limit]


def fetch_github_bounties(limit: int = 20) -> list[Listing]:
    q = 'is:issue is:open (label:bounty OR label:"💎 Bounty" OR label:algora)'
    url = f"https://api.github.com/search/issues?q={q.replace(' ', '+')}&per_page={min(limit, 30)}"
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = get_json("github_bounties", url, headers=headers)
    if not isinstance(data, dict):
        raise PolicyError("github_bounties: unexpected payload")
    out: list[Listing] = []
    for item in data.get("items") or []:
        html = _s(item, "html_url")
        out.append(
            Listing(
                id=listing_id("github_bounties", html),
                source="github_bounties",
                title=_s(item, "title"),
                url=html,
                company=_s(item, "repository_url").rsplit("/", 2)[-2] if _s(item, "repository_url") else "",
                description=redact(_s(item, "body")[:4000]),
                tags=["bounty"],
                fetched_at=utc_now(),
                extra={"repo_url": _s(item, "repository_url"), "number": item.get("number")},
            )
        )
    return out[:limit]


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


REGISTRY: dict[str, Fetcher] = {
    "github_issues": fetch_github_issues,
    "github_bounties": fetch_github_bounties,
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "jobicy": fetch_jobicy,
    "himalayas": fetch_himalayas,
    "working_nomads": fetch_working_nomads,
}
