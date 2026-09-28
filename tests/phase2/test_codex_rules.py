"""Codex execpolicy `.rules` validation.

Invokes the real `codex execpolicy check` binary on the generated rules file
and asserts the policy parses + a few representative commands match the
expected decisions.

Skips with an explicit reason if the `codex` binary is not on PATH (so the
test suite still runs in CI containers that don't ship codex).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentos_cli.core.adapter_compiler import compile_all


CODEX = shutil.which("codex")

pytestmark = pytest.mark.skipif(
    CODEX is None, reason="codex CLI not installed; execpolicy gate cannot run"
)


def _run(rules: Path, *cmd: str) -> dict:
    proc = subprocess.run(
        [CODEX, "execpolicy", "check", "--rules", str(rules), *cmd],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"codex execpolicy check exit={proc.returncode}\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}"
    )
    # stdout is JSON
    return json.loads(proc.stdout)


@pytest.fixture()
def rules_file(tmp_agent_os: Path) -> Path:
    compile_all(tmp_agent_os)
    p = tmp_agent_os / "generated" / "codex" / "rules" / "agentic-os.rules"
    assert p.is_file()
    return p


def test_codex_execpolicy_check_parses(rules_file: Path) -> None:
    """Pass a no-op command (`:`) just to validate the rules parse."""
    out = _run(rules_file, ":")
    assert "matchedRules" in out


def test_codex_rules_allow_git_status(rules_file: Path) -> None:
    out = _run(rules_file, "git", "status")
    assert out.get("decision") == "allow", out


def test_codex_rules_forbid_rm_rf_root(rules_file: Path) -> None:
    out = _run(rules_file, "rm", "-rf", "/")
    assert out.get("decision") == "forbidden", out


def test_codex_rules_prompt_git_push(rules_file: Path) -> None:
    out = _run(rules_file, "git", "push", "origin", "main")
    # git push is in prompt rules in shell-policy.yaml
    assert out.get("decision") == "prompt", out


def test_codex_rules_no_match_is_unmatched(rules_file: Path) -> None:
    out = _run(rules_file, "definitely-not-a-real-binary-xyz")
    # No rule matches → matchedRules empty, no top-level decision.
    assert out.get("matchedRules") == [] or out.get("matchedRules") is None
