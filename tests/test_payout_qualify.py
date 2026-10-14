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


def test_assigned_bounty_is_marked_claimed():
    q = qualify(
        _listing(
            title="Flaky e2e test",
            description="Reward $500",
            tags=["bounty"],
            extra={"assignees": ["someone"]},
        )
    )
    assert q.verdict == "reject"
    assert any("already assigned" in d for d in q.disqualifiers)


def test_assigned_non_bounty_is_not_penalised():
    q = qualify(
        _listing(
            title="Fix the flaky e2e test",
            description="Reproduce the bug and add regression coverage.",
            tags=["good first issue"],
            extra={"assignees": ["someone"]},
        )
    )
    assert not any("already assigned" in d for d in q.disqualifiers)


def test_bounty_label_amount_counts_into_payout():
    # GitHub bounties often put the amount in a label ("$1.2k", "$780").
    q = qualify(
        _listing(
            title="Automate Bug Detection",
            description="Find bugs and file issues.",
            tags=["bounty", "$780", "$1k", "$1.2k"],
        )
    )
    assert q.payout_usd == 1200


def test_mirror_repost_is_demoted():
    q = qualify(
        _listing(
            title="[Bounty $3,000] Fix sampling bias",
            url="https://github.com/plaza/agg/issues/1836",
            description=(
                "### 赏金平台\n### 原始链接 / Source URL "
                "https://github.com/real/repo/issues/59732\n"
                "[Bounty $3,000] Fix sampling bias"
            ),
            tags=["bounty"],
        )
    )
    assert q.verdict == "needs_human"
    assert any("mirror" in r for r in q.reasons)


def test_self_reference_is_not_a_mirror():
    q = qualify(
        _listing(
            title="Flaky e2e test",
            url="https://github.com/acme/widgets/issues/5",
            description="See source url https://github.com/acme/widgets/issues/5 for context.",
            tags=["bounty"],
        )
    )
    assert not any("mirror" in r for r in q.reasons)


