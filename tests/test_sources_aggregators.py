from __future__ import annotations

import pytest

from qa_copilot.discover import sources
from qa_copilot.policy import PolicyError


def _fake(monkeypatch, responder):
    """Replace get_json; record calls; dispatch on url."""
    calls: list[dict] = []

    def fake(source_id, url, *, headers=None, timeout=30.0):
        calls.append({"source": source_id, "url": url, "headers": headers or {}})
        return responder(url)

    monkeypatch.setattr(sources, "get_json", fake)
    return calls


def test_arbeitnow_filters_qa_and_dedupes(monkeypatch):
    payload = {
        "data": [
            {"title": "Software Engineer in Test", "company_name": "Luma", "url": "https://a/1",
             "description": "<p>QA smoke</p>", "tags": ["qa"], "job_types": [], "location": "Berlin"},
            {"title": "Software Engineer in Test", "company_name": "Luma", "url": "https://a/2",
             "description": "<p>QA smoke</p>", "tags": [], "job_types": [], "location": "Munich"},
            {"title": "Marketing Manager", "company_name": "Luma", "url": "https://a/3",
             "description": "growth", "tags": [], "job_types": [], "location": "Berlin"},
        ]
    }
    _fake(monkeypatch, lambda url: payload)
    out = sources.fetch_arbeitnow(limit=10)
    assert len(out) == 1  # QA only, and the duplicate city posting collapses
    assert out[0].title == "Software Engineer in Test"
    assert out[0].url == "https://a/1"
    assert "<p>" not in out[0].description


def test_fourdayweek_maps_locations(monkeypatch):
    payload = {"jobs": [
        {"title": "QA Engineer", "slug": "qa-engineer", "category": "qa", "schedule_type": "4_day_week",
         "level": "mid", "company_name": "Acme", "locations": [{"city": "Tokyo", "country": "Japan"}]},
        {"title": "Designer", "slug": "d", "category": "design", "locations": []},
    ]}
    _fake(monkeypatch, lambda url: payload)
    out = sources.fetch_fourdayweek(limit=10)
    assert len(out) == 1
    assert out[0].url == "https://4dayweek.io/job/qa-engineer"
    assert "Tokyo" in out[0].extra["locations"]


def test_careerjet_sends_referer_and_covers_locales(monkeypatch):
    payload = {"jobs": [{"title": "QA テスト", "url": "https://cj/1", "company": "X",
                         "description": "<b>QA</b>", "locations": "Tokyo"}]}
    calls = _fake(monkeypatch, lambda url: payload)
    monkeypatch.setenv("CAREERJET_LOCALES", "ja_JP,en_GB")
    out = sources.fetch_careerjet(limit=10)
    assert calls and all("Referer" in c["headers"] for c in calls)
    locales = {
        c["url"].split("locale_code=")[1].split("&", 1)[0] for c in calls
    }
    assert locales == {"ja_JP", "en_GB"}
    assert out and out[0].extra["locale"]


def test_adzuna_requires_key(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    with pytest.raises(PolicyError, match="ADZUNA_APP_ID"):
        sources.fetch_adzuna(limit=5)


def test_adzuna_reads_results(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    monkeypatch.setenv("ADZUNA_COUNTRIES", "jp")
    payload = {"results": [
        {"title": "QA Engineer", "redirect_url": "https://adz/1", "description": "test",
         "company": {"display_name": "Acme"}, "location": {"display_name": "Tokyo"}, "category": {"tag": "it"}},
    ]}
    _fake(monkeypatch, lambda url: payload)
    out = sources.fetch_adzuna(limit=5)
    assert out and out[0].company == "Acme"
    assert out[0].extra["country"] == "jp"


def test_hn_hiring_uses_role_headers(monkeypatch):
    def responder(url):
        if "search_by_date" in url:
            return {"hits": [
                {"objectID": "1", "title": "Ask HN: Who wants to be hired? (October 2026)"},
                {"objectID": "999", "title": "Ask HN: Who is hiring? (October 2026)"},
            ]}
        return {"hits": [
            {"objectID": "10", "comment_text": "Acme | SDET | Remote | $150k"},
            {"objectID": "11", "comment_text": "Globex | Growth Marketing Manager | Remote"},
            {"objectID": "12", "comment_text": "Initech | Test Automation Engineer | Berlin"},
        ]}

    calls = _fake(monkeypatch, responder)
    out = sources.fetch_hn_hiring(limit=10)
    titles = [x.title for x in out]
    assert any("SDET" in t for t in titles)
    assert any("Test Automation" in t for t in titles)
    assert all("Growth Marketing" not in t for t in titles)
    assert any("story_999" in c["url"] for c in calls)


def test_hn_hiring_errors_without_thread(monkeypatch):
    _fake(monkeypatch, lambda url: {"hits": []})
    with pytest.raises(PolicyError, match="Who is hiring"):
        sources.fetch_hn_hiring(limit=5)
