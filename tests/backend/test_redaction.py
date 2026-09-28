from app.services.redaction import REDACTED, redact


def test_aws_access_key_redacted():
    s = "leaked: AKIAABCDEFGHIJKLMNOP rest"
    assert "AKIA" not in redact(s)
    assert REDACTED in redact(s)


def test_github_pat_redacted():
    s = "token=ghp_" + "a" * 36
    out = redact(s)
    assert "ghp_" not in out
    assert REDACTED in out


def test_openai_key_redacted():
    s = "use sk-" + "B" * 30
    out = redact(s)
    assert "sk-" not in out


def test_keyvalue_pairs_redacted():
    for kv in [
        "password=hunter2",
        "secret: topsecret",
        "TOKEN=abcdef",
        "api_key=xyz",
        "api-key='quoted-value'",
    ]:
        out = redact(kv)
        assert REDACTED in out
        assert "hunter2" not in out
        assert "topsecret" not in out
        assert "abcdef" not in out
        assert "xyz" not in out
        assert "quoted-value" not in out


def test_bearer_redacted():
    assert REDACTED in redact("Authorization: Bearer abc.def-123")


def test_empty():
    assert redact("") == ""


def test_clean_text_unchanged():
    s = "totally benign sentence with no secrets."
    assert redact(s) == s
