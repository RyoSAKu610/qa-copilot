"""Hard policy for marketplace access.

User config may only *restrict* a source. It cannot upgrade paste-only
to HTTP, cannot enable a disabled source, and cannot turn on writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

RESEARCHED = "2026-08-28"


class AccessMode(str, Enum):
    OFFICIAL_API = "official_api"
    PASTE_ONLY = "paste_only"
    DISABLED = "disabled"


class WriteMode(str, Enum):
    NEVER = "never"
    APPROVAL_REQUIRED = "approval_required"


@dataclass(frozen=True)
class SourcePolicy:
    id: str
    display_name: str
    access: AccessMode
    write: WriteMode
    ai_summary: str
    notes: str
    docs: tuple[str, ...] = ()
    attribution_required: bool = False
    allow_http_hosts: tuple[str, ...] = ()
    researched: str = RESEARCHED
    # Opt-in sources are OFFICIAL_API but are skipped by a bare `discover`.
    # They usually cost money or carry extra responsibility, so the operator
    # must ask for them by name (`discover --source apify`) or enable them in
    # config. Config can turn one on; it still cannot turn a disabled source on.
    default_enabled: bool = True


class PolicyError(RuntimeError):
    pass


# Access rules are code, not config. Config cannot make these looser.
SOURCES: dict[str, SourcePolicy] = {
    "github_issues": SourcePolicy(
        id="github_issues",
        display_name="GitHub Issues",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.APPROVAL_REQUIRED,
        ai_summary="Official REST/Search API. Machine accounts allowed if a human owns them. HTML scraping is not used.",
        notes="Comments/PRs require a signed approval packet. No bulk issue spam.",
        docs=(
            "https://docs.github.com/en/site-policy/github-terms/github-terms-of-service",
            "https://docs.github.com/en/rest",
        ),
        allow_http_hosts=("api.github.com", "github.com"),
    ),
    "github_bounties": SourcePolicy(
        id="github_bounties",
        display_name="GitHub bounty-labelled issues",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.APPROVAL_REQUIRED,
        ai_summary="Same as GitHub Issues. Search uses official API labels (bounty, 💎 Bounty).",
        notes="Claiming a bounty is a GitHub comment or PR. Packet only; human posts it.",
        docs=("https://docs.github.com/en/rest/search/search",),
        allow_http_hosts=("api.github.com", "github.com"),
    ),
    "remotive": SourcePolicy(
        id="remotive",
        display_name="Remotive public jobs API",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Public jobs API intended for sharing listings. Attribution required. Do not republish onto other job boards.",
        notes="Read-only. Apply on Remotive in a browser. Rate limit: stay under 2 req/min.",
        docs=("https://github.com/remotive-com/remote-jobs-api",),
        attribution_required=True,
        allow_http_hosts=("remotive.com",),
    ),
    "remoteok": SourcePolicy(
        id="remoteok",
        display_name="Remote OK public API",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Public /api feed. Link back to Remote OK. Feed is delayed ~24h.",
        notes="Read-only. Do not use the Remote OK logo.",
        docs=("https://remoteok.com/api",),
        attribution_required=True,
        allow_http_hosts=("remoteok.com", "remoteok.io"),
    ),
    "jobicy": SourcePolicy(
        id="jobicy",
        display_name="Jobicy public API",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Documented public remote-jobs API.",
        notes="Read-only discovery.",
        docs=("https://jobicy.com/api/v2/remote-jobs",),
        attribution_required=True,
        allow_http_hosts=("jobicy.com",),
    ),
    "himalayas": SourcePolicy(
        id="himalayas",
        display_name="Himalayas public jobs API",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Public jobs JSON API.",
        notes="Read-only discovery.",
        docs=("https://himalayas.app/jobs/api",),
        attribution_required=True,
        allow_http_hosts=("himalayas.app",),
    ),
    "working_nomads": SourcePolicy(
        id="working_nomads",
        display_name="Working Nomads exposed jobs",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Public JSON feed at /api/exposed_jobs/.",
        notes="Read-only discovery.",
        docs=("https://www.workingnomads.com/api/exposed_jobs/",),
        attribution_required=True,
        allow_http_hosts=("www.workingnomads.com", "workingnomads.com"),
    ),
    "arbeitnow": SourcePolicy(
        id="arbeitnow",
        display_name="Arbeitnow job board API",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Documented public job-board JSON feed published by Arbeitnow for other boards to consume.",
        notes="Read-only discovery. Apply on the original listing. Feed is heavy; fetch with a limit.",
        docs=("https://www.arbeitnow.com/blog/job-board-api",),
        attribution_required=True,
        allow_http_hosts=("arbeitnow.com", "www.arbeitnow.com"),
    ),
    "fourdayweek": SourcePolicy(
        id="fourdayweek",
        display_name="4 Day Week job board API",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Public jobs JSON backing the 4dayweek.io board.",
        notes="Read-only discovery. Apply on the original listing.",
        docs=("https://4dayweek.io/",),
        attribution_required=True,
        allow_http_hosts=("4dayweek.io",),
    ),
    "careerjet": SourcePolicy(
        id="careerjet",
        display_name="Careerjet public search API",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Public aggregator search API covering many locales (ja_JP, en_GB, en_US, ...). Requires a Referer header identifying the caller and an affiliate id.",
        notes="Read-only. Set CAREERJET_AFFID (default 0) and CAREERJET_LOCALES. Served over http only.",
        docs=("https://www.careerjet.com/partners/api/",),
        attribution_required=True,
        allow_http_hosts=("public.api.careerjet.net",),
    ),
    "adzuna": SourcePolicy(
        id="adzuna",
        display_name="Adzuna jobs API",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Official Adzuna search API. Country-parameterised, so the same source covers English and Japanese markets.",
        notes="Read-only. Set ADZUNA_APP_ID / ADZUNA_APP_KEY (free) and ADZUNA_COUNTRIES (default jp,gb,us).",
        docs=("https://developer.adzuna.com/",),
        attribution_required=True,
        allow_http_hosts=("api.adzuna.com",),
    ),
    "hn_hiring": SourcePolicy(
        id="hn_hiring",
        display_name="Hacker News 'Who is hiring'",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary="Public Algolia HN Search API. Reads the monthly 'Ask HN: Who is hiring?' thread and its comments. No HTML scraping of news.ycombinator.com.",
        notes="Read-only discovery. Posts usually include salary and often remote QA roles. Reply by email; never auto-post to HN.",
        docs=("https://hn.algolia.com/api", "https://news.ycombinator.com/"),
        attribution_required=True,
        allow_http_hosts=("hn.algolia.com",),
    ),
    "apify": SourcePolicy(
        id="apify",
        display_name="Apify actors (hosted scrapers)",
        access=AccessMode.OFFICIAL_API,
        write=WriteMode.NEVER,
        ai_summary=(
            "This tool speaks only to the official Apify API (api.apify.com), never to the marketplace "
            "directly. Apify runs a third-party actor (hosted scraper) and returns its dataset, which this "
            "tool reads and ranks. It is a paid, opt-in discovery path for marketplaces that have no public "
            "jobs API (Upwork, Lancers, Coconala, Indeed, LinkedIn, Google Jobs, ...)."
        ),
        notes=(
            "OPT-IN and read-only discovery. The target site's Terms of Service still apply to whatever the "
            "actor fetches; using a hosted scraper does not launder a ToS violation, and the account-ban risk "
            "is yours to accept. This source never logs in, never applies, never bids, never messages: it only "
            "pulls listings you then work through the normal human gate. You pay Apify per result, so keep "
            "`--limit` small. Configure APIFY_TOKEN and (optionally) APIFY_CHANNELS; see the README."
        ),
        docs=(
            "https://docs.apify.com/api/v2",
            "https://apify.com/store",
            "https://docs.apify.com/platform/actors/running/actors-in-store",
        ),
        attribution_required=False,
        allow_http_hosts=("api.apify.com",),
        default_enabled=False,
    ),
    "paste": SourcePolicy(
        id="paste",
        display_name="Manual paste inbox",
        access=AccessMode.PASTE_ONLY,
        write=WriteMode.APPROVAL_REQUIRED,
        ai_summary="User pastes a job they already viewed in a browser. No HTTP to the origin marketplace.",
        notes="Use this for CrowdWorks, Lancers, Coconala, Upwork, Freelancer.com UI copy.",
        docs=(),
    ),
    "crowdworks": SourcePolicy(
        id="crowdworks",
        display_name="CrowdWorks",
        access=AccessMode.PASTE_ONLY,
        write=WriteMode.APPROVAL_REQUIRED,
        ai_summary="Platform AI policy does not ban AI; client agreement and transparency required. No public worker job API. Do not scrape.",
        notes="Paste the listing you opened yourself. Never auto-apply. Disclose AI if the client asks or the brief is silent and you will use AI.",
        docs=(
            "https://blog.crowdworks.jp/archives/5811/",
            "https://crowdworks.jp/pages/guidelines/job_offer",
            "https://crowdworks.jp/pages/agreement",
        ),
    ),
    "lancers": SourcePolicy(
        id="lancers",
        display_name="Lancers",
        access=AccessMode.PASTE_ONLY,
        write=WriteMode.APPROVAL_REQUIRED,
        ai_summary="Client can mark generative-AI allowed/restricted. Auto-proposal was retired in favor of confirm-then-propose. Site content reuse and high-load access are prohibited.",
        notes="Paste only. Human submits any proposal. Honor the job's AI flag.",
        docs=(
            "https://www.lancers.jp/help/terms",
            "https://info.lancers.jp/34546",
        ),
    ),
    "coconala": SourcePolicy(
        id="coconala",
        display_name="Coconala",
        access=AccessMode.PASTE_ONLY,
        write=WriteMode.APPROVAL_REQUIRED,
        ai_summary="AI illustrations are restricted. AI articles/photos have conditions. Automated use of Coconala features is prohibited. Auto-responders on purchased content are prohibited.",
        notes="Do not HTTP-automate Coconala. Paste a brief you copied. Human talks in the token room.",
        docs=(
            "https://help.coconala.com/hc/ja/articles/48479864968729",
            "https://coconala.com/pages/terms_user",
            "https://coconala.com/news/1127",
        ),
    ),
    "upwork": SourcePolicy(
        id="upwork",
        display_name="Upwork",
        access=AccessMode.PASTE_ONLY,
        write=WriteMode.APPROVAL_REQUIRED,
        ai_summary="Unauthorized bots, scrapers, extensions, and faster-than-human UI automation are banned, and auto-submitting proposals is banned. Copying a listing you already opened into a local tool and sending a proposal by hand is not automation, so this tool accepts pasted Upwork text but still never speaks HTTP to Upwork.",
        notes="Paste only. This tool does not contact Upwork. Auto-bid stays impossible: you send the proposal yourself in the official UI.",
        docs=(
            "https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly",
            "https://www.upwork.com/legal#terms",
        ),
    ),
    "freelancer_com": SourcePolicy(
        id="freelancer_com",
        display_name="Freelancer.com",
        access=AccessMode.DISABLED,
        write=WriteMode.NEVER,
        ai_summary="An official API exists, but bidding/messaging through it is out of scope for this minimal build. Circumventing rate limits is banned.",
        notes="Disabled until a human adds an official token *and* keeps bid placement behind approval. Not implemented.",
        docs=(
            "https://www.freelancer.com/about/apiterms",
            "https://developers.freelancer.com/docs/",
        ),
    ),
    "usertesting": SourcePolicy(
        id="usertesting",
        display_name="UserTesting",
        access=AccessMode.DISABLED,
        write=WriteMode.NEVER,
        ai_summary="Contributor Code of Conduct forbids AI-generated responses on the platform. Discovery is possible, but the deliverable would be non-compliant, so this tool does not ingest it.",
        notes="Kept disabled on purpose: it is not the discovery that is the problem, it is that an AI-drafted test result cannot be submitted. Use a human-only workflow for uTest.",
        docs=(
            "https://participant-support.usertesting.com/hc/en-us/articles/37395412977427-Contributor-Code-of-Conduct",
        ),
    ),
    "utest": SourcePolicy(
        id="utest",
        display_name="uTest / Applause",
        access=AccessMode.DISABLED,
        write=WriteMode.NEVER,
        ai_summary="Emulators, simulators, remote machines, and jailbroken devices are banned unless staff instruct otherwise. Tests expect a real human device and often webcam/voice.",
        notes="Not an agent-fit source.",
        docs=("https://www.utest.com/rules-of-engagement",),
    ),
    "hackerone": SourcePolicy(
        id="hackerone",
        display_name="HackerOne",
        access=AccessMode.DISABLED,
        write=WriteMode.NEVER,
        ai_summary="AI-assisted research is allowed. Fully autonomous hackbots and unverified/slop submissions are not. Human must validate a real PoC before submit.",
        notes="This QA tool does not hunt or submit bounties. Use a dedicated security workflow with scope + human validation.",
        docs=("https://www.hackerone.com/policies/code-of-conduct",),
    ),
    "bugcrowd": SourcePolicy(
        id="bugcrowd",
        display_name="Bugcrowd",
        access=AccessMode.DISABLED,
        write=WriteMode.NEVER,
        ai_summary="Unvalidated AI submissions are treated as slop. Submission farming is banned. Human researcher is accountable.",
        notes="Not implemented. Do not auto-submit.",
        docs=(
            "https://www.bugcrowd.com/blog/bugcrowd-policy-changes-to-address-ai-slop-submissions/",
        ),
    ),
}


def get_source(source_id: str) -> SourcePolicy:
    if source_id not in SOURCES:
        raise PolicyError(f"unknown source: {source_id}")
    return SOURCES[source_id]


def effective(source_id: str, user_enabled: dict[str, bool] | None = None) -> SourcePolicy:
    policy = get_source(source_id)
    if user_enabled and user_enabled.get(source_id) is False:
        return SourcePolicy(
            id=policy.id,
            display_name=policy.display_name,
            access=AccessMode.DISABLED,
            write=WriteMode.NEVER,
            ai_summary=policy.ai_summary,
            notes="Disabled in local config.",
            docs=policy.docs,
            attribution_required=policy.attribution_required,
            allow_http_hosts=policy.allow_http_hosts,
            researched=policy.researched,
            default_enabled=policy.default_enabled,
        )
    return policy


def assert_http_allowed(source_id: str, url: str, user_enabled: dict[str, bool] | None = None) -> None:
    policy = effective(source_id, user_enabled)
    if policy.access is not AccessMode.OFFICIAL_API:
        raise PolicyError(
            f"{source_id}: HTTP fetch is not allowed (mode={policy.access.value}). "
            "Use paste inbox or open the site yourself."
        )
    host = (urlparse(url).hostname or "").lower()
    if host not in policy.allow_http_hosts:
        raise PolicyError(
            f"{source_id}: host {host!r} is not in the allowlist {policy.allow_http_hosts}"
        )


def assert_write_allowed(source_id: str, approved: bool) -> None:
    policy = get_source(source_id)
    if policy.write is WriteMode.NEVER:
        raise PolicyError(f"{source_id}: outbound writes are never allowed from this tool")
    if policy.write is WriteMode.APPROVAL_REQUIRED and not approved:
        raise PolicyError(f"{source_id}: human approval required before any outbound packet")


def discoverable_source_ids(user_enabled: dict[str, bool] | None = None) -> list[str]:
    out: list[str] = []
    for sid in SOURCES:
        policy = effective(sid, user_enabled)
        if policy.access is not AccessMode.OFFICIAL_API:
            continue
        # Opt-in sources stay out of a bare `discover` until the operator asks
        # for them by name or flips them on in config.
        if not policy.default_enabled and not (user_enabled or {}).get(sid):
            continue
        out.append(sid)
    return out


def paste_source_ids() -> list[str]:
    return [sid for sid, p in SOURCES.items() if p.access is AccessMode.PASTE_ONLY]
