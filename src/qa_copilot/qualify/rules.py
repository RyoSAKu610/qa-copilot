from __future__ import annotations

import re

from qa_copilot.models import Listing, Qualification, utc_now
from qa_copilot.policy import get_source
from qa_copilot.redact import redact

from .payout import extract_payout

# Agent-shaped QA work this tool is actually built to help with.
POSITIVE = [
    (r"\b(qa|q\.?a\.?|quality assurance|test(?:ing|er)?|e2e|end[- ]to[- ]end)\b", "QA/testing language"),
    (r"\b(bug|defect|regression|repro(?:duce)?|flaky)\b", "bug reproduction"),
    (r"\b(playwright|cypress|selenium|pytest|jest)\b", "automation stack"),
    (r"\b(a11y|accessibility|wcag|axe-core)\b", "accessibility"),
    (r"\b(api test|contract test|postman|openapi)\b", "API testing"),
    (r"\b(test plan|test case|qa report|bug report)\b", "QA artifacts"),
    (r"(テスト|品質|不具合|バグ|再現|検証|デバッグ)", "Japanese QA terms"),
    (r"\b(good first issue|help wanted|documentation)\b", "OSS issue fit"),
]

DISQUALIFY = [
    (r"no\s*(gen(erative)?)?\s*ai|ai\s*(use|usage)?\s*(is\s*)?(not\s*)?(allowed|prohibited|forbidden)|生成ai禁止|ai使用不可|chatgpt.*禁止", "AI explicitly forbidden"),
    (r"(口コミ代行|レビュー投稿|ステルスマーケティング|like for like|follower growth)", "review/engagement farming"),
    (r"(webcam|face recording|自撮り|顔出し|think out loud)", "webcam / spoken usability test"),
    (r"(来社必須|来社あり|常駐必須|常駐あり|\bonsite\b|\bon-site\b|in[- ]office only)", "must be physically present"),
    (r"(スクレイピング|crawl the site|scrape (the )?(site|data))", "asks for scraping"),
    (r"(アカウント作成代行|create accounts in bulk)", "account mill"),
    (r"usertesting\.com|contributor network", "UserTesting-style human panel"),
]


def _blob(listing: Listing) -> str:
    parts = [
        listing.title,
        listing.company,
        listing.description,
        " ".join(listing.tags),
        listing.extra.get("raw", "") if isinstance(listing.extra.get("raw"), str) else "",
    ]
    return redact(" \n ".join(p for p in parts if p)).lower()


def qualify(listing: Listing) -> Qualification:
    text = _blob(listing)
    reasons: list[str] = []
    agent_fit: list[str] = []
    disqualifiers: list[str] = []
    score = 20

    payout_usd, payout_note = extract_payout(
        listing.title,
        listing.description,
        listing.extra.get("raw") if isinstance(listing.extra.get("raw"), str) else "",
        listing.extra.get("salary") if isinstance(listing.extra.get("salary"), str) else "",
    )

    policy = get_source(listing.source) if listing.source else None
    if policy and policy.access.value == "disabled":
        disqualifiers.append(f"source {listing.source} is disabled by policy")
        score = 0

    if listing.client_allows_ai == "no":
        disqualifiers.append("client_allows_ai=no")
        score = 0

    for pat, label in DISQUALIFY:
        if re.search(pat, text, re.I):
            disqualifiers.append(label)
            score = 0

    for pat, label in POSITIVE:
        if re.search(pat, text, re.I):
            agent_fit.append(label)
            score += 12

    if listing.test_target and listing.permission_to_test:
        agent_fit.append("explicit test target + permission")
        score += 15
    elif listing.test_target and not listing.permission_to_test:
        reasons.append("test_target present but permission_to_test is false — plan only, do not hit the URL")

    if listing.source.startswith("github"):
        agent_fit.append("GitHub issue can be reproduced in a clone")
        score += 10

    if listing.source in {"crowdworks", "lancers", "coconala"} and not listing.ai_disclosed:
        reasons.append("JP marketplace paste: disclose AI use before applying unless the client already allowed it")

    if payout_usd is not None:
        agent_fit.append(f"payout {payout_note}")
        # A stated payout is a real signal that the work is scoped and funded.
        score += 10
        if payout_usd >= 150:
            score += 10

    score = max(0, min(100, score))

    if disqualifiers:
        verdict = "reject"
        reasons = disqualifiers + reasons
    elif score >= 45 and agent_fit:
        verdict = "candidate"
        reasons = [f"score {score}"] + agent_fit + reasons
    else:
        verdict = "needs_human"
        reasons = [f"score {score} — not an obvious QA-agent fit"] + agent_fit + reasons

    return Qualification(
        listing_id=listing.id,
        score=score,
        verdict=verdict,
        reasons=reasons,
        agent_fit=agent_fit,
        disqualifiers=disqualifiers,
        qualified_at=utc_now(),
        payout_usd=payout_usd,
        payout_note=payout_note,
    )
