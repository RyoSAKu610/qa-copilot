from __future__ import annotations

import pytest

from qa_copilot.policy import (
    AccessMode,
    PolicyError,
    assert_http_allowed,
    assert_write_allowed,
    effective,
    get_source,
)


def test_crowdworks_cannot_be_fetched():
    with pytest.raises(PolicyError, match="HTTP fetch is not allowed"):
        assert_http_allowed("crowdworks", "https://crowdworks.jp/public/jobs/1")


def test_lancers_cannot_be_fetched():
    with pytest.raises(PolicyError, match="HTTP fetch is not allowed"):
        assert_http_allowed("lancers", "https://www.lancers.jp/work/detail/1")


def test_upwork_is_paste_only_never_http():
    # Upwork bans bots, so this tool must never speak HTTP to it. A human may
    # still paste a listing they already opened (that is not automation).
    assert get_source("upwork").access is AccessMode.PASTE_ONLY
    with pytest.raises(PolicyError):
        assert_http_allowed("upwork", "https://www.upwork.com/jobs/~1")
    with pytest.raises(PolicyError, match="approval"):
        assert_write_allowed("upwork", approved=False)
    assert_write_allowed("upwork", approved=True)


def test_upwork_not_discoverable():
    from qa_copilot.policy import discoverable_source_ids

    assert "upwork" not in discoverable_source_ids()


def test_new_aggregators_are_official_api():
    for sid in ("arbeitnow", "fourdayweek", "careerjet", "adzuna", "hn_hiring"):
        assert get_source(sid).access is AccessMode.OFFICIAL_API


def test_new_aggregators_block_foreign_hosts():
    with pytest.raises(PolicyError, match="allowlist"):
        assert_http_allowed("adzuna", "https://evil.example/jobs")
    assert_http_allowed("adzuna", "https://api.adzuna.com/v1/api/jobs/jp/search/1")
    assert_http_allowed("hn_hiring", "https://hn.algolia.com/api/v1/search")


def test_usertesting_disabled():
    assert get_source("usertesting").access is AccessMode.DISABLED


def test_config_cannot_enable_a_disabled_source():
    # usertesting is hard-disabled; config can only ever narrow, never widen.
    policy = effective("usertesting", {"usertesting": True})
    assert policy.access is AccessMode.DISABLED


def test_config_cannot_promote_paste_to_http():
    # upwork is paste_only now; config still cannot make it fetchable.
    policy = effective("upwork", {"upwork": True})
    assert policy.access is AccessMode.PASTE_ONLY
    with pytest.raises(PolicyError):
        assert_http_allowed("upwork", "https://www.upwork.com/jobs/~1", {"upwork": True})


def test_config_can_disable_github():
    policy = effective("github_issues", {"github_issues": False})
    assert policy.access is AccessMode.DISABLED
    with pytest.raises(PolicyError):
        assert_http_allowed("github_issues", "https://api.github.com/search/issues", {"github_issues": False})


def test_github_wrong_host_blocked():
    with pytest.raises(PolicyError, match="allowlist"):
        assert_http_allowed("github_issues", "https://evil.example/github")


def test_github_api_host_ok():
    assert_http_allowed("github_issues", "https://api.github.com/search/issues")


def test_write_requires_approval():
    with pytest.raises(PolicyError, match="approval"):
        assert_write_allowed("github_issues", approved=False)
    assert_write_allowed("github_issues", approved=True)


def test_remotive_never_writes():
    with pytest.raises(PolicyError, match="never"):
        assert_write_allowed("remotive", approved=True)
