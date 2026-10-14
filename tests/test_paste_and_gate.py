from __future__ import annotations

from pathlib import Path

import pytest

from qa_copilot.approve.gate import approve, build_packet
from qa_copilot.discover.paste import parse_paste
from qa_copilot.execute.runner import execute
from qa_copilot.policy import PolicyError, assert_http_allowed
from qa_copilot.qualify.rules import qualify
from qa_copilot.report.renderer import render_report
from qa_copilot.store import Workspace


def test_parse_crowdworks_paste(tmp_path: Path):
    src = Path("examples/paste-crowdworks.md")
    listing = parse_paste(src)
    assert listing.source == "crowdworks"
    q = qualify(listing)
    assert q.verdict in {"candidate", "needs_human"}


def test_parse_upwork_paste_is_allowed_but_never_http(tmp_path: Path):
    # Upwork now accepts pasted listings (human copied it), but the tool still
    # refuses to talk HTTP to Upwork.
    p = tmp_path / "up.md"
    p.write_text("---\nsource: upwork\ntitle: x\n---\nhello\n", encoding="utf-8")
    listing = parse_paste(p)
    assert listing.source == "upwork"
    with pytest.raises(PolicyError):
        assert_http_allowed("upwork", "https://www.upwork.com/jobs/~1")


def test_parse_usertesting_paste_still_blocked(tmp_path: Path):
    p = tmp_path / "ut.md"
    p.write_text("---\nsource: usertesting\ntitle: x\n---\nhello\n", encoding="utf-8")
    with pytest.raises(PolicyError, match="disabled"):
        parse_paste(p)


def test_packet_requires_approval(tmp_path: Path):
    ws = Workspace(tmp_path / "ws")
    listing = parse_paste(Path("examples/paste-crowdworks.md"))
    ws.save_listing(listing)
    with pytest.raises(PolicyError, match="approve"):
        build_packet(ws, listing)


def test_approve_requires_checklist(tmp_path: Path):
    ws = Workspace(tmp_path / "ws")
    listing = parse_paste(Path("examples/paste-crowdworks.md"))
    ws.save_listing(listing)
    with pytest.raises(PolicyError, match="checklist"):
        approve(ws, listing, "ada", {})


def test_full_local_pipeline(tmp_path: Path):
    ws = Workspace(tmp_path / "ws")
    fixture = Path("fixtures/site/broken.html").resolve()
    paste = tmp_path / "job.md"
    paste.write_text(
        "\n".join(
            [
                "---",
                "source: paste",
                "title: Local fixture QA",
                f"test_target: file:{fixture}",
                "permission_to_test: true",
                "client_allows_ai: yes",
                "ai_disclosed: true",
                "---",
                "Run accessibility smoke on the attached fixture.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    listing = parse_paste(paste)
    ws.save_listing(listing)
    q = qualify(listing)
    ws.save_qualification(q)
    assert q.verdict == "candidate"
    run = execute(ws, listing)
    titles = [f.title for f in run.findings]
    assert any("alt" in t for t in titles)
    assert any("button" in t.lower() or "unnamed" in t.lower() or "accessible name" in t.lower() for t in titles)
    render_report(ws, listing, q, run)
    approve(
        ws,
        listing,
        "ada",
        {
            "i_read_the_report": True,
            "i_verified_or_dropped_unverified_findings": True,
            "i_accept_the_target_platform_terms": True,
            "i_will_submit_manually": True,
            "i_will_disclose_ai_if_required": True,
        },
    )
    path = build_packet(ws, listing)
    text = Path(path).read_text(encoding="utf-8")
    assert "does not send" in text.lower() or "does not send it anywhere" in text
