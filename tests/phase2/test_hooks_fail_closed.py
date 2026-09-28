"""Fail-closed guarantees on every generated hook script.

For each generated hook (Claude, Gemini, Codex), feed:
  * empty stdin
  * malformed bytes (`b"<<<not json>>>"`)
  * 5MB random payload
  * a JSON object with reserved/prototype-pollution keys (`__proto__`, etc.)
  * a non-object JSON value (a bare integer)

Every one MUST be denied. For Claude/Codex (exit-code semantics): non-zero
exit. For Gemini (JSON-deny semantics): exit 0 with ``{"decision": "deny"}``
on stdout.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

from agentos_cli.core.adapter_compiler import compile_all


HOOK_KIND = {
    "claude/hooks/pre_tool_use.py": "exit_nonzero",
    "claude/hooks/pre_file_write.py": "exit_nonzero",
    "claude/hooks/session_start.py": "exit_nonzero",
    "codex/hooks/tool_before.py": "exit_nonzero",
    "gemini/hooks/before_tool.py": "json_deny",
}


@pytest.fixture()
def hooks(tmp_agent_os: Path) -> dict[str, Path]:
    compile_all(tmp_agent_os)
    gen = tmp_agent_os / "generated"
    paths: dict[str, Path] = {}
    for rel in HOOK_KIND:
        p = gen / rel
        assert p.is_file(), f"missing hook: {p}"
        paths[rel] = p
    return paths


def _run_hook(hook_path: Path, stdin_bytes: bytes, cwd: Path, env: dict | None = None):
    proc_env = dict(os.environ)
    # Ensure the hook can import agentos_cli (repo root on PYTHONPATH).
    repo_root = str(Path(__file__).resolve().parents[2])
    pp = proc_env.get("PYTHONPATH", "")
    proc_env["PYTHONPATH"] = repo_root + (os.pathsep + pp if pp else "")
    if env:
        proc_env.update(env)
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_bytes,
        capture_output=True,
        cwd=str(cwd),
        env=proc_env,
        timeout=30,
    )


def _assert_denied(hook_rel: str, proc: subprocess.CompletedProcess) -> None:
    kind = HOOK_KIND[hook_rel]
    if kind == "exit_nonzero":
        # Claude/Codex: deny is non-zero exit (specifically 2 in our template,
        # but we accept any non-zero).
        assert proc.returncode != 0, (
            f"{hook_rel} expected non-zero exit on bad input;\n"
            f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
        )
    elif kind == "json_deny":
        # Gemini: exit 0 with JSON deny on stdout.
        assert proc.returncode == 0, (
            f"{hook_rel} Gemini hook must exit 0; got {proc.returncode}\n"
            f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
        )
        try:
            data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            pytest.fail(f"{hook_rel} expected JSON on stdout; got {proc.stdout!r}")
        assert data.get("decision") == "deny", (
            f"{hook_rel} expected decision=deny; got {data!r}"
        )
    else:
        pytest.fail(f"unknown HOOK_KIND for {hook_rel}: {kind!r}")


@pytest.mark.parametrize("hook_rel", list(HOOK_KIND.keys()))
def test_empty_stdin_denied(tmp_agent_os: Path, hooks: dict[str, Path], hook_rel: str) -> None:
    proc = _run_hook(hooks[hook_rel], b"", tmp_agent_os.parent)
    _assert_denied(hook_rel, proc)


@pytest.mark.parametrize("hook_rel", list(HOOK_KIND.keys()))
def test_malformed_bytes_denied(tmp_agent_os: Path, hooks: dict[str, Path], hook_rel: str) -> None:
    proc = _run_hook(hooks[hook_rel], b"<<<not json>>>", tmp_agent_os.parent)
    _assert_denied(hook_rel, proc)


@pytest.mark.parametrize("hook_rel", list(HOOK_KIND.keys()))
def test_giant_payload_denied(tmp_agent_os: Path, hooks: dict[str, Path], hook_rel: str) -> None:
    # 5 MB of random bytes — well over the 1MB cap.
    payload = secrets.token_bytes(5 * 1024 * 1024)
    proc = _run_hook(hooks[hook_rel], payload, tmp_agent_os.parent)
    _assert_denied(hook_rel, proc)


@pytest.mark.parametrize("hook_rel", list(HOOK_KIND.keys()))
def test_prototype_pollution_denied(tmp_agent_os: Path, hooks: dict[str, Path], hook_rel: str) -> None:
    body = json.dumps({"__proto__": {"x": 1}, "tool_name": "Bash"}).encode("utf-8")
    proc = _run_hook(hooks[hook_rel], body, tmp_agent_os.parent)
    _assert_denied(hook_rel, proc)


@pytest.mark.parametrize("hook_rel", list(HOOK_KIND.keys()))
def test_non_object_payload_denied(tmp_agent_os: Path, hooks: dict[str, Path], hook_rel: str) -> None:
    # A bare integer is valid JSON but not an object.
    proc = _run_hook(hooks[hook_rel], b"42", tmp_agent_os.parent)
    _assert_denied(hook_rel, proc)


@pytest.mark.parametrize("hook_rel", list(HOOK_KIND.keys()))
def test_invalid_utf8_denied(tmp_agent_os: Path, hooks: dict[str, Path], hook_rel: str) -> None:
    proc = _run_hook(hooks[hook_rel], b"\xff\xfe\xff\xfe", tmp_agent_os.parent)
    _assert_denied(hook_rel, proc)


# --- positive controls: a well-formed allow path actually allows ---

def test_claude_pre_tool_use_allows_git_status(tmp_agent_os: Path, hooks: dict[str, Path]) -> None:
    body = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}}).encode("utf-8")
    proc = _run_hook(
        hooks["claude/hooks/pre_tool_use.py"],
        body,
        tmp_agent_os.parent,
        env={"CLAUDE_PROJECT_DIR": str(tmp_agent_os.parent)},
    )
    assert proc.returncode == 0, f"expected allow exit=0, got {proc.returncode}; stderr={proc.stderr!r}"


def test_claude_pre_tool_use_blocks_rm_rf(tmp_agent_os: Path, hooks: dict[str, Path]) -> None:
    body = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}).encode("utf-8")
    proc = _run_hook(
        hooks["claude/hooks/pre_tool_use.py"],
        body,
        tmp_agent_os.parent,
        env={"CLAUDE_PROJECT_DIR": str(tmp_agent_os.parent)},
    )
    assert proc.returncode == 2, f"expected deny exit=2, got {proc.returncode}"
    assert b"forbid" in proc.stdout or b"deny" in proc.stdout


def test_gemini_before_tool_denies_rm_rf(tmp_agent_os: Path, hooks: dict[str, Path]) -> None:
    body = json.dumps({"tool_name": "Shell", "tool_input": {"command": "rm -rf /"}}).encode("utf-8")
    proc = _run_hook(
        hooks["gemini/hooks/before_tool.py"],
        body,
        tmp_agent_os.parent,
        env={"GEMINI_PROJECT_DIR": str(tmp_agent_os.parent)},
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout.decode("utf-8"))
    assert data["decision"] == "deny", data
