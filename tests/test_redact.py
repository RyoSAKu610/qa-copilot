from qa_copilot.redact import redact


def test_redacts_tokens():
    text = "Authorization: Bearer abcdefghijklmnop token=supersecret"
    out = redact(text)
    assert "supersecret" not in out
    assert "abcdefghijklmnop" not in out
    assert "[REDACTED]" in out


def test_redacts_github_pat():
    out = redact("key ghp_abcdefghijklmnopqrstuvwxyz123456")
    assert "ghp_" not in out
