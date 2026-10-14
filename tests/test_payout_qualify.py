from __future__ import annotations

from qa_copilot.models import Listing
from qa_copilot.qualify.rules import qualify


def _listing(**kw) -> Listing:
    base = dict(
        id="x",
        source="github_bounties",
        title="Fix flaky Playwright e2e test and add regression coverage",
        description="Reproduce the bug, write a test plan, a11y smoke.",
    )
    base.update(kw)
    return Listing(**base)  # type: ignore[arg-type]


def test_payout_is_recorded_and_boosts_score():
    body = "Reproduce the bug, write a test plan, a11y smoke."
    plain = qualify(_listing(description=body))
    paid = qualify(_listing(description=body + " Bounty: $500 on merge."))
    assert paid.payout_usd == 500
    assert plain.payout_usd is None
    assert paid.score > plain.score
    assert any("payout" in f for f in paid.agent_fit)


def test_big_payout_scores_higher_than_small():
    def make(amount: int):
        return qualify(
            Listing(
                id="x",
                source="paste",
                title="QA report",
                description=f"Write a qa report. Bounty ${amount}.",
            )
        )

    small = make(50)
    big = make(800)
    assert small.payout_usd == 50
    assert big.payout_usd == 800
    assert big.score > small.score


def test_no_payout_is_none():
    q = qualify(_listing())
    assert q.payout_usd is None
    assert q.payout_note == ""


def test_disqualifier_still_rejects_even_with_payout():
    q = qualify(_listing(description="Bounty $900. 生成AI禁止。"))
    assert q.verdict == "reject"
    assert q.disqualifiers


def test_bounty_label_lets_a_bare_amount_count():
    q = qualify(
        _listing(
            title="Crash on save",
            description="The app crashes. We pay $300 on merge.",
            tags=["bounty"],
        )
    )
    assert q.payout_usd == 300
