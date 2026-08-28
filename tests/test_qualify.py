from __future__ import annotations

from qa_copilot.models import Listing
from qa_copilot.qualify.rules import qualify


def test_playwright_qa_is_candidate():
    listing = Listing(
        id="a",
        source="paste",
        title="Playwright E2E regression and bug reports",
        description="Write test cases, reproduce bugs, a11y checks.",
    )
    q = qualify(listing)
    assert q.verdict == "candidate"
    assert q.score >= 45
    assert q.agent_fit


def test_review_farm_rejected():
    listing = Listing(
        id="b",
        source="crowdworks",
        title="口コミ代行と高評価レビュー投稿",
        description="食べログにレビュー投稿してください",
    )
    q = qualify(listing)
    assert q.verdict == "reject"
    assert q.disqualifiers


def test_ai_forbidden_rejected():
    listing = Listing(
        id="c",
        source="paste",
        title="QA test plan",
        description="生成AI禁止。人手のみ。",
        client_allows_ai="unknown",
    )
    q = qualify(listing)
    assert q.verdict == "reject"


def test_remote_ok_phrase_is_not_onsite():
    listing = Listing(
        id="e",
        source="crowdworks",
        title="テスト項目作成",
        description="来社不要、リモートで不具合を再現してください。",
    )
    q = qualify(listing)
    assert "must be physically present" not in q.disqualifiers
    assert q.verdict != "reject"


def test_client_flag_no_ai():
    listing = Listing(
        id="d",
        source="lancers",
        title="テスト項目作成",
        description="テスト項目を作ってください",
        client_allows_ai="no",
    )
    q = qualify(listing)
    assert q.verdict == "reject"
