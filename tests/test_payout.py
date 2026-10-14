from __future__ import annotations

from qa_copilot.qualify.payout import extract_payout


def test_dollar_amount():
    amount, note = extract_payout("Bounty: $500 for fixing the flaky login test")
    assert amount == 500
    assert "500" in note


def test_usd_suffix():
    amount, _ = extract_payout("We pay 1,200 usd on merge")
    assert amount == 1200


def test_usd_prefix_and_k():
    assert extract_payout("USD 2.5k bounty")[0] == 2500


def test_no_money_language_is_not_a_payout():
    assert extract_payout("Write 40 tests for issue #300") == (None, "")


def test_picks_the_largest_amount():
    amount, note = extract_payout("Reward $100, bonus $1,500 on merge")
    assert amount == 1500
    assert "saw 2" in note


def test_japanese_reward():
    amount, _ = extract_payout("報酬は$200です")
    assert amount == 200


def test_dust_is_ignored():
    # "$2" is not a real bounty; do not let it rank the listing.
    assert extract_payout("bounty $2") == (None, "")


def test_salary_is_not_a_bounty():
    assert extract_payout("Senior QA Engineer | $140K-$160K + equity | Remote") == (None, "")
    assert extract_payout("QA Engineer | $30/hr | Contract") == (None, "")
    assert extract_payout("Compensation: $250,000 annually") == (None, "")


def test_bounty_label_relaxes_context():
    # A labelled bounty: a bare amount with a currency marker counts anywhere.
    assert extract_payout("Fix the flaky test. Reward: $400", bounty_context=True)[0] == 400
    assert extract_payout("We will send you $300", bounty_context=True)[0] == 300
    # A currency marker is still required: "300 tests" is not a payout.
    assert extract_payout("write 300 tests", bounty_context=True) == (None, "")
    # And dust is still dust.
    assert extract_payout("tip jar $3", bounty_context=True) == (None, "")


def test_donation_is_not_a_bounty():
    assert extract_payout("Donate $10-$100 USDT to support us", bounty_context=True) == (None, "")
    assert extract_payout("Sponsor us: $50/month", bounty_context=True) == (None, "")


def test_empty_input():
    assert extract_payout("", "") == (None, "")
