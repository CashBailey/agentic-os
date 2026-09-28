from app.services.policy_eval import evaluate_file, evaluate_mcp, evaluate_shell


POLICY = {
    "shell": {
        "default": "prompt",
        "forbidden": [{"pattern": ["rm", "-rf", "/"], "reason": "x"}],
        "prompt": [{"pattern": ["git", "push"], "reason": "publish"}],
        "allow": [
            {"pattern": ["git", "status"]},
            {"pattern": ["rg", "*"]},
            {"pattern": ["sed", "-n", "*"]},
        ],
    },
    "files": {"protected": [".env", "*.pem", "agent-os/private/**"]},
    "mcp": {"default": "deny-write", "allow_read": ["docs"], "allow_write": []},
}


def test_forbid_wins():
    r = evaluate_shell(["rm", "-rf", "/"], POLICY)
    assert r["decision"] == "deny"


def test_prompt_match():
    r = evaluate_shell(["git", "push"], POLICY)
    assert r["decision"] == "prompt"


def test_allow_exact():
    r = evaluate_shell(["git", "status"], POLICY)
    assert r["decision"] == "allow"


def test_wildcard_one_token():
    r = evaluate_shell(["rg", "foo"], POLICY)
    assert r["decision"] == "allow"


def test_wildcard_trailing_star_matches_zero():
    r = evaluate_shell(["sed", "-n"], POLICY)
    # trailing * matches zero-or-more
    assert r["decision"] == "allow"


def test_wildcard_trailing_star_matches_many():
    r = evaluate_shell(["sed", "-n", "1,10p", "file.txt"], POLICY)
    assert r["decision"] == "allow"


def test_unmatched_uses_default():
    r = evaluate_shell(["curl", "https://example.com"], POLICY)
    assert r["decision"] == "prompt"


def test_file_protected():
    assert evaluate_file(".env", POLICY)["decision"] == "deny"
    assert evaluate_file("foo.pem", POLICY)["decision"] == "deny"


def test_file_unprotected():
    assert evaluate_file("README.md", POLICY)["decision"] == "allow"


def test_mcp_read_allowed():
    assert evaluate_mcp("docs", "read", POLICY)["decision"] == "allow"


def test_mcp_write_default_denied():
    assert evaluate_mcp("docs", "write", POLICY)["decision"] == "deny"
