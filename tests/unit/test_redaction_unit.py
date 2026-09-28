"""Unit tests for backend/app/services/redaction.py."""
from __future__ import annotations

import pytest

from app.services.redaction import REDACTED, redact, redact_many


class TestEmptyAndPassthrough:
    def test_empty_string_returns_empty(self):
        assert redact("") == ""

    def test_none_passthrough(self):
        # The function uses `if not text: return text` -> None returns None
        assert redact(None) is None  # type: ignore[arg-type]

    def test_no_secrets_unchanged(self):
        s = "hello world, nothing sensitive here"
        assert redact(s) == s


class TestAwsKey:
    def test_aws_key_redacted(self):
        s = "key=AKIAABCDEFGHIJKLMNOP and more"
        # key= will trigger the key=value pattern; the value gets [REDACTED].
        out = redact(s)
        assert "AKIAABCDEFGHIJKLMNOP" not in out
        assert REDACTED in out

    def test_aws_key_bare(self):
        s = "Plain AKIAABCDEFGHIJKLMNOP here"
        out = redact(s)
        assert "AKIAABCDEFGHIJKLMNOP" not in out
        assert REDACTED in out

    def test_aws_too_short_not_redacted(self):
        s = "AKIAshort"  # not 16 trailing chars
        assert redact(s) == s


class TestGitHubToken:
    def test_ghp_token_redacted(self):
        token = "ghp_" + "A" * 36
        s = f"token: {token} here"
        out = redact(s)
        assert token not in out
        assert REDACTED in out

    def test_ghp_too_short_not_redacted(self):
        s = "ghp_short"
        assert redact(s) == s


class TestOpenAiKey:
    def test_sk_key_redacted(self):
        s = "use sk-" + "x" * 30
        out = redact(s)
        assert "sk-" + "x" * 30 not in out
        assert REDACTED in out

    def test_sk_too_short_not_redacted(self):
        s = "sk-short"  # less than 20 chars after sk-
        assert redact(s) == s


class TestKeyValuePair:
    @pytest.mark.parametrize(
        "key",
        ["password", "PASSWORD", "secret", "Secret", "token", "TOKEN",
         "api_key", "api-key", "API_KEY", "Api-Key"],
    )
    def test_key_equals_value(self, key):
        s = f"{key}=hunter2"
        out = redact(s)
        assert "hunter2" not in out
        assert REDACTED in out
        # key preserved
        assert key.split("=")[0].lower() in out.lower()

    def test_key_colon_value(self):
        s = "password: hunter2"
        out = redact(s)
        assert "hunter2" not in out

    def test_quoted_value(self):
        s = 'password="hunter2"'
        out = redact(s)
        assert "hunter2" not in out
        assert REDACTED in out


class TestBearerToken:
    def test_bearer_redacted(self):
        s = "Authorization: Bearer abc.DEF-123_xyz"
        out = redact(s)
        assert "abc.DEF-123_xyz" not in out
        assert REDACTED in out

    def test_bearer_case_insensitive(self):
        s = "bearer myToken123"
        out = redact(s)
        assert "myToken123" not in out


class TestMultipleSecrets:
    def test_multiple_in_one_string(self):
        token = "ghp_" + "B" * 36
        s = f"AKIAABCDEFGHIJKLMNOP and {token} and password=foo"
        out = redact(s)
        assert "AKIAABCDEFGHIJKLMNOP" not in out
        assert token not in out
        assert "foo" not in out
        assert out.count(REDACTED) >= 3


class TestRedactMany:
    def test_redacts_each_element(self):
        items = ["password=a", "nothing", "Bearer x.y.z"]
        out = redact_many(items)
        assert len(out) == 3
        assert "a" not in out[0] or REDACTED in out[0]
        assert out[1] == "nothing"
        assert "x.y.z" not in out[2]

    def test_empty_list(self):
        assert redact_many([]) == []
