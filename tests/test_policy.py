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


def test_upwork_is_disabled():
    assert get_source("upwork").access is AccessMode.DISABLED
    with pytest.raises(PolicyError):
        assert_http_allowed("upwork", "https://www.upwork.com/jobs/~1")


def test_usertesting_disabled():
    assert get_source("usertesting").access is AccessMode.DISABLED


def test_config_cannot_enable_upwork():
    policy = effective("upwork", {"upwork": True})
    assert policy.access is AccessMode.DISABLED


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
