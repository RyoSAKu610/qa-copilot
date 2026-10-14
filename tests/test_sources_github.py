from __future__ import annotations

from qa_copilot.discover import sources


def _item(title: str, url: str, body: str = "", labels=()):
    return {
        "title": title,
        "html_url": url,
        "body": body,
        "repository_url": "https://api.github.com/repos/acme/widgets",
        "number": 1,
        "labels": [{"name": x} for x in labels],
    }


def test_github_queries_never_or_labels(monkeypatch):
    """GitHub 422s on `OR` between qualifiers, so no query may contain OR+label."""
    seen: list[str] = []

    def fake(source_id, query, limit):
        seen.append(query)
        return []

    monkeypatch.setattr(sources, "_github_search", fake)
    sources.fetch_github_issues(limit=5)
    sources.fetch_github_bounties(limit=5)
    assert seen
    for query in seen:
        assert " OR " not in query.upper()
        assert "is:issue" in query and "is:open" in query


def test_github_issues_filters_non_qa(monkeypatch):
    items = [
        _item("Add dark mode", "https://github.com/acme/w/issues/1"),
        _item("Flaky login test", "https://github.com/acme/w/issues/2", body="repro steps"),
    ]
    monkeypatch.setattr(sources, "_github_search", lambda s, q, l: items)
    out = sources.fetch_github_issues(limit=10)
    assert [x.title for x in out] == ["Flaky login test"]


def test_github_bounties_searches_each_label_and_dedupes(monkeypatch):
    calls: list[str] = []

    def fake(source_id, query, limit):
        calls.append(query)
        # Same issue returned by both labels must appear once.
        return [_item("Crash on save", "https://github.com/acme/w/issues/9", "defect")]

    monkeypatch.setattr(sources, "_github_search", fake)
    out = sources.fetch_github_bounties(limit=10)
    assert len(calls) == len(sources.BOUNTY_LABELS)
    assert len(out) == 1
    assert "bounty" in out[0].tags
