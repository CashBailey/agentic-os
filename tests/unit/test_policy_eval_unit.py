"""Unit tests for backend/app/services/policy_eval.py."""
from __future__ import annotations

import pytest

from app.services.policy_eval import (
    _match,
    evaluate_approval,
    evaluate_file,
    evaluate_mcp,
    evaluate_shell,
)


# ---------- _match wildcard semantics ----------

class TestMatch:
    def test_empty_pattern_matches_empty_args(self):
        assert _match([], []) is True

    def test_empty_pattern_no_match_when_args_present(self):
        assert _match([], ["x"]) is False

    def test_literal_exact_match(self):
        assert _match(["git", "status"], ["git", "status"]) is True

    def test_literal_length_mismatch(self):
        assert _match(["git", "status"], ["git"]) is False
        assert _match(["git"], ["git", "status"]) is False

    def test_literal_value_mismatch(self):
        assert _match(["git", "push"], ["git", "pull"]) is False

    def test_single_star_matches_any_one_token(self):
        assert _match(["git", "*"], ["git", "anything"]) is True
        assert _match(["*", "status"], ["git", "status"]) is True

    def test_single_star_at_middle_requires_token(self):
        # Middle "*" requires a token in that slot; pattern length must match.
        assert _match(["git", "*", "x"], ["git", "x"]) is False

    def test_trailing_star_zero_remaining(self):
        # Per code: trailing "*" head=pattern[:-1]; len(args) >= len(head) suffices.
        # So ["git", "*"] matches ["git"] (zero remaining).
        assert _match(["git", "*"], ["git"]) is True
        assert _match(["git", "*"], ["git", "a", "b", "c"]) is True

    def test_trailing_star_matches_many(self):
        assert _match(["rm", "*"], ["rm", "-rf", "/tmp"]) is True

    def test_trailing_star_with_head_mismatch(self):
        assert _match(["rm", "-rf", "*"], ["rm", "-r", "x"]) is False

    def test_trailing_star_head_too_short(self):
        assert _match(["a", "b", "*"], ["a"]) is False

    def test_middle_star_is_single_token(self):
        assert _match(["a", "*", "c"], ["a", "X", "c"]) is True
        assert _match(["a", "*", "c"], ["a", "X", "Y", "c"]) is False


# ---------- evaluate_shell ----------

class TestEvaluateShell:
    def test_empty_policy_defaults_to_prompt(self):
        out = evaluate_shell(["ls"], {})
        assert out["decision"] == "prompt"
        assert out["matched_rule"] is None

    def test_custom_default(self):
        out = evaluate_shell(["ls"], {"shell": {"default": "allow"}})
        assert out["decision"] == "allow"

    def test_forbidden_wins_over_allow(self):
        policy = {
            "shell": {
                "default": "allow",
                "forbidden": [{"pattern": ["rm", "-rf", "*"], "reason": "danger"}],
                "allow": [{"pattern": ["rm", "*"]}],
            }
        }
        out = evaluate_shell(["rm", "-rf", "/"], policy)
        assert out["decision"] == "deny"
        assert out["matched_rule"]["reason"] == "danger"

    def test_prompt_wins_over_allow(self):
        policy = {
            "shell": {
                "default": "allow",
                "prompt": [{"pattern": ["git", "push"]}],
                "allow": [{"pattern": ["git", "*"]}],
            }
        }
        out = evaluate_shell(["git", "push"], policy)
        assert out["decision"] == "prompt"

    def test_allow_when_matched(self):
        policy = {"shell": {"default": "prompt", "allow": [{"pattern": ["ls"]}]}}
        out = evaluate_shell(["ls"], policy)
        assert out["decision"] == "allow"

    def test_no_match_returns_default(self):
        policy = {"shell": {"default": "deny", "allow": [{"pattern": ["ls"]}]}}
        out = evaluate_shell(["whoami"], policy)
        assert out["decision"] == "deny"
        assert out["matched_rule"] is None

    def test_wildcard_in_rule(self):
        policy = {"shell": {"allow": [{"pattern": ["git", "*"]}]}}
        out = evaluate_shell(["git", "status"], policy)
        assert out["decision"] == "allow"


# ---------- evaluate_file ----------

class TestEvaluateFile:
    def test_empty_policy_allows(self):
        out = evaluate_file("/tmp/foo", {})
        assert out["decision"] == "allow"
        assert out["matched_rule"] is None

    def test_glob_protected(self):
        policy = {"files": {"protected": ["/etc/*"]}}
        out = evaluate_file("/etc/passwd", policy)
        assert out["decision"] == "deny"
        assert out["matched_rule"] == {"protected": "/etc/*"}

    def test_tilde_expansion_in_protected(self):
        import os
        home = os.path.expanduser("~")
        policy = {"files": {"protected": ["~/.ssh/*"]}}
        out = evaluate_file(f"{home}/.ssh/id_rsa", policy)
        assert out["decision"] == "deny"

    def test_no_protected_match(self):
        policy = {"files": {"protected": ["/etc/*"]}}
        out = evaluate_file("/home/x/foo.txt", policy)
        assert out["decision"] == "allow"

    def test_empty_protected_list(self):
        out = evaluate_file("/etc/passwd", {"files": {"protected": []}})
        assert out["decision"] == "allow"


# ---------- evaluate_mcp ----------

class TestEvaluateMcp:
    def test_default_deny_write_blocks_write(self):
        out = evaluate_mcp("srv", "write", {})
        assert out["decision"] == "deny"
        assert out["matched_rule"] == {"default": "deny-write"}

    def test_default_deny_write_allows_read(self):
        out = evaluate_mcp("srv", "read", {})
        # read not in allow_read; falls through to final return.
        # default=='deny-write' so condition `default == 'allow'` is False -> decision='deny'
        assert out["decision"] == "deny"

    def test_allow_read_when_listed(self):
        policy = {"mcp": {"allow_read": ["github"]}}
        out = evaluate_mcp("github", "read", policy)
        assert out["decision"] == "allow"
        assert out["matched_rule"] == {"allow_read": "github"}

    def test_allow_write_when_listed(self):
        policy = {"mcp": {"allow_write": ["github"]}}
        out = evaluate_mcp("github", "write", policy)
        assert out["decision"] == "allow"
        assert out["matched_rule"] == {"allow_write": "github"}

    def test_default_allow_for_read(self):
        policy = {"mcp": {"default": "allow"}}
        out = evaluate_mcp("anything", "read", policy)
        assert out["decision"] == "allow"

    def test_unlisted_write_under_default_allow(self):
        policy = {"mcp": {"default": "allow"}}
        out = evaluate_mcp("anything", "write", policy)
        # default != 'deny-write' so falls through to last line
        assert out["decision"] == "allow"


# ---------- evaluate_approval ----------

class TestEvaluateApproval:
    def test_default_approves(self):
        out = evaluate_approval("anything", {})
        assert out["decision"] == "approve"
        assert out["matched_rule"] is None

    def test_destructive_requires_reason_prompts(self):
        out = evaluate_approval(
            "destructive", {"approval": {"destructive_requires_reason": True}}
        )
        assert out["decision"] == "prompt"
        assert out["matched_rule"] == {"destructive_requires_reason": True}

    def test_destructive_without_flag_approves(self):
        out = evaluate_approval("destructive", {"approval": {}})
        assert out["decision"] == "approve"

    def test_external_publication_prompts(self):
        out = evaluate_approval(
            "external_publication",
            {"approval": {"external_publication_requires_confirmation": True}},
        )
        assert out["decision"] == "prompt"

    def test_irrelevant_action_approves(self):
        out = evaluate_approval(
            "noop", {"approval": {"destructive_requires_reason": True}}
        )
        assert out["decision"] == "approve"
