from __future__ import annotations

import json

import pytest

from qa_copilot.discover import sources
from qa_copilot.policy import (
    AccessMode,
    PolicyError,
    assert_http_allowed,
    discoverable_source_ids,
    get_source,
)


def _fake_post(monkeypatch, responder):
    """Replace post_json; record (url, payload) per call."""
    calls: list[dict] = []

    def fake(source_id, url, payload, *, headers=None, timeout=120.0):
        calls.append({"source": source_id, "url": url, "payload": payload})
        return responder(url, payload)

    monkeypatch.setattr(sources, "post_json", fake)
    return calls


@pytest.fixture(autouse=True)
def _apify_token(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-token")


def test_apify_is_official_api_but_opt_in():
    policy = get_source("apify")
    assert policy.access is AccessMode.OFFICIAL_API
    assert policy.write.value == "never"
    # Costs money and scrapes via a third party, so a bare `discover` skips it.
    assert "apify" not in discoverable_source_ids()
    assert "apify" in discoverable_source_ids({"apify": True})


def test_apify_only_talks_to_its_own_host():
    assert_http_allowed("apify", "https://api.apify.com/v2/acts/x/run-sync-get-dataset-items")
    with pytest.raises(PolicyError, match="allowlist"):
        assert_http_allowed("apify", "https://www.upwork.com/jobs/~1")
    # ... and the marketplace ids themselves still refuse HTTP outright.
    with pytest.raises(PolicyError, match="not allowed"):
        assert_http_allowed("upwork", "https://www.upwork.com/jobs/~1")
    with pytest.raises(PolicyError, match="not allowed"):
        assert_http_allowed("crowdworks", "https://crowdworks.jp/public/jobs/1")


def test_post_json_refuses_a_foreign_host_without_touching_the_network():
    # assert_http_allowed runs before any socket is opened, so this is offline.
    with pytest.raises(PolicyError, match="allowlist"):
        sources.post_json("apify", "https://evil.example/run", {})


def test_apify_requires_a_token(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "")
    monkeypatch.setenv("APIFY_API_TOKEN", "")
    with pytest.raises(PolicyError, match="APIFY_TOKEN"):
        sources.fetch_apify(limit=5)


def test_apify_normalizes_aliases_and_filters_to_qa(monkeypatch):
    payload = [
        # QA-ish row using alternate field names (no 'title'/'url' keys).
        {"positionName": "QA Automation Engineer", "jobUrl": "https://up/1",
         "companyName": "Acme", "descriptionText": "<p>Playwright regression</p>",
         "salary": "$60/hr", "city": "Tokyo"},
        # Non-QA row must be dropped by the local filter.
        {"title": "Growth Marketer", "url": "https://up/2", "company": "Acme",
         "description": "funnel optimisation"},
        # Row with no title at all.
        {"url": "https://up/3", "description": "QA"},
        # Duplicate of the first row (same URL) collapses.
        {"title": "QA Automation Engineer", "url": "https://up/1", "company": "Acme",
         "description": "Playwright"},
    ]
    _fake_post(monkeypatch, lambda url, payload_in: payload)
    out = sources.fetch_apify(limit=10)

    assert len(out) == 1, [o.title for o in out]
    row = out[0]
    assert row.source == "apify"
    assert row.title == "QA Automation Engineer"
    assert row.url == "https://up/1"
    assert row.company == "Acme"
    assert "<p>" not in row.description
    assert row.extra["salary"] == "$60/hr"
    assert row.extra["location"] == "Tokyo"
    assert row.extra["apify_channel"] == "apify_upwork"
    assert "Apify actor" in row.attribution


def test_apify_renders_limit_and_query_into_the_input(monkeypatch):
    calls = _fake_post(monkeypatch, lambda url, payload_in: [])
    sources.fetch_apify(limit=3)

    assert len(calls) >= 1
    first = calls[0]
    assert first["url"].startswith("https://api.apify.com/v2/acts/")
    assert "token=" in first["url"]
    # Bare "{limit}" must become an int, "{query}" becomes the channel query.
    assert first["payload"]["maxItems"] == 3
    assert first["payload"]["searchQuery"] == "QA tester"


def test_apify_accepts_a_json_list_result(monkeypatch):
    _fake_post(monkeypatch, lambda url, payload_in: [
        {"title": "SDET", "url": "https://up/9", "description": "automation testing", "company": "Z"}
    ])
    out = sources.fetch_apify(limit=5)
    assert len(out) == 1 and out[0].title == "SDET"


def test_apify_channel_override_is_honoured(monkeypatch):
    monkeypatch.setenv(
        "APIFY_CHANNELS",
        json.dumps([{
            "id": "only",
            "actor": "somebody~custom-actor",
            "locale": "ja",
            "query": "テスト",
            "input": {"q": "{query}", "maxItems": "{limit}"},
        }]),
    )
    calls = _fake_post(monkeypatch, lambda url, payload_in: [])
    sources.fetch_apify(limit=7)
    assert len(calls) == 1
    assert "somebody~custom-actor" in calls[0]["url"] or "somebody%7Ecustom-actor" in calls[0]["url"]
    assert calls[0]["payload"] == {"q": "テスト", "maxItems": 7}


def test_apify_rejects_a_malformed_channel_override(monkeypatch):
    monkeypatch.setenv("APIFY_CHANNELS", "{not json")
    with pytest.raises(PolicyError, match="not valid JSON"):
        sources.fetch_apify(limit=5)

    monkeypatch.setenv("APIFY_CHANNELS", json.dumps([{"no_actor": True}]))
    with pytest.raises(PolicyError, match="actor"):
        sources.fetch_apify(limit=5)

    monkeypatch.setenv("APIFY_CHANNELS", json.dumps([]))
    with pytest.raises(PolicyError, match="non-empty"):
        sources.fetch_apify(limit=5)


def test_apify_actor_failure_names_the_actor(monkeypatch):
    def boom(source_id, url, payload, *, headers=None, timeout=120.0):
        raise RuntimeError("actor exited 1")

    monkeypatch.setattr(sources, "post_json", boom)
    with pytest.raises(PolicyError, match="neatrat~upwork-job-scraper"):
        sources.fetch_apify(limit=5)


def test_apify_is_registered_for_discover(monkeypatch):
    assert "apify" in sources.REGISTRY
    # Make sure a missing token fails politely instead of hitting the network.
    monkeypatch.setenv("APIFY_TOKEN", "")
    monkeypatch.setenv("APIFY_API_TOKEN", "")
    from qa_copilot.discover.registry import run_discover

    with pytest.raises(PolicyError, match="APIFY_TOKEN"):
        run_discover(["apify"], limit=5, user_enabled=None)
