"""Tests for `agentos validate`."""
from __future__ import annotations

import io
import json
import shutil
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from agentos_cli.cli import main


def _run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_validate_known_good(agent_os_root: Path) -> None:
    rc, out = _run([
        "validate",
        "--agent-os-root", str(agent_os_root),
        "--json",
    ])
    assert rc == 0, out
    payload = json.loads(out)
    assert payload["valid"] is True, payload


def test_validate_not_initialized(tmp_path: Path) -> None:
    empty_dir = tmp_path / "nope"
    rc, out = _run([
        "validate",
        "--agent-os-root", str(empty_dir),
        "--json",
    ])
    assert rc == 2
    payload = json.loads(out)
    assert payload["valid"] is False


def test_validate_flags_missing_required(tmp_path: Path, agent_os_root: Path) -> None:
    # Copy the agent-os tree, then delete one required file.
    copy = tmp_path / "agent-os"
    shutil.copytree(agent_os_root, copy)
    (copy / "context" / "global" / "user.md").unlink()
    rc, out = _run([
        "validate",
        "--agent-os-root", str(copy),
        "--json",
    ])
    assert rc == 1
    payload = json.loads(out)
    assert payload["valid"] is False
    assert any("user.md" in e["file"] for e in payload["errors"])


def test_validate_flags_malformed_yaml(tmp_path: Path, agent_os_root: Path) -> None:
    copy = tmp_path / "agent-os"
    shutil.copytree(agent_os_root, copy)
    bad = copy / "workflows" / "session-start.md"
    bad.write_text("---\nname: session-start\nbad: [unclosed\n---\nbody\n", encoding="utf-8")
    rc, out = _run([
        "validate",
        "--agent-os-root", str(copy),
        "--json",
    ])
    assert rc == 1
    payload = json.loads(out)
    assert any("session-start.md" in e["file"] for e in payload["errors"])
