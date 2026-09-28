"""Tests for `agentos sync`."""
from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from agentos_cli.cli import main


def _run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_sync_dry_run_writes_nothing(tmp_path: Path, agent_os_root: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    rc, out = _run([
        "sync",
        "--agent-os-root", str(agent_os_root),
        "--target", str(target),
        "--mode", "dry-run",
        "--json",
    ])
    assert rc == 0
    payload = json.loads(out)
    assert payload["mode"] == "dry-run"
    assert {f["target"] for f in payload["files"]} == {
        str(target / "CLAUDE.md"),
        str(target / "GEMINI.md"),
        str(target / "AGENTS.md"),
    }
    # Nothing on disk
    assert list(target.iterdir()) == []


def test_sync_copy_creates_files(tmp_path: Path, agent_os_root: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    rc, out = _run([
        "sync",
        "--agent-os-root", str(agent_os_root),
        "--target", str(target),
        "--mode", "copy",
        "--json",
    ])
    assert rc == 0
    for name in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        assert (target / name).is_file()


def test_sync_deterministic(tmp_path: Path, agent_os_root: Path) -> None:
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    t1.mkdir()
    t2.mkdir()
    _run(["sync", "--agent-os-root", str(agent_os_root), "--target", str(t1), "--mode", "copy"])
    _run(["sync", "--agent-os-root", str(agent_os_root), "--target", str(t2), "--mode", "copy"])
    for name in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        assert (t1 / name).read_bytes() == (t2 / name).read_bytes()


def test_sync_backup_on_overwrite(tmp_path: Path, agent_os_root: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "CLAUDE.md").write_text("OLD CONTENT", encoding="utf-8")
    rc, _ = _run([
        "sync",
        "--agent-os-root", str(agent_os_root),
        "--target", str(target),
        "--mode", "copy",
        "--backup",
    ])
    assert rc == 0
    backups = list(target.glob("CLAUDE.md.bak.*"))
    assert backups, "expected backup file to be created"
    assert backups[0].read_text(encoding="utf-8") == "OLD CONTENT"
