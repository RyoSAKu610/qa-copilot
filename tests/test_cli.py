from __future__ import annotations

from qa_copilot.cli import main


def test_policy_command(capsys):
    assert main(["policy"]) == 0
    out = capsys.readouterr().out
    assert "crowdworks" in out
    assert "paste_only" in out
    assert "upwork" in out
    assert "disabled" in out
