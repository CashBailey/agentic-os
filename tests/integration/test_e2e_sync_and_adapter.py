"""End-to-end smoke tests for `agentos sync` and `agentos install-adapter`.

These tests invoke the installed CLI via subprocess against a temp target
directory using the repo's canonical agent-os/ tree as the source.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _agentos_bin() -> str:
    # Prefer the venv's agentos if present.
    venv_bin = REPO_ROOT / ".venv" / "bin" / "agentos"
    if venv_bin.exists():
        return str(venv_bin)
    return "agentos"


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_e2e_sync_writes_three_files(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    out = subprocess.run(
        [_agentos_bin(), "sync", "--project", "demo", "--target", str(target),
         "--mode", "copy", "--backup"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert out.returncode == 0, out.stderr
    for name in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        assert (target / name).exists(), f"missing {name}"


def test_e2e_sync_is_deterministic(tmp_path: Path) -> None:
    t1 = tmp_path / "t1"; t1.mkdir()
    t2 = tmp_path / "t2"; t2.mkdir()
    for tgt in (t1, t2):
        r = subprocess.run(
            [_agentos_bin(), "sync", "--project", "demo", "--target", str(tgt),
             "--mode", "copy"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        assert r.returncode == 0, r.stderr
    for name in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        assert _hash(t1 / name) == _hash(t2 / name), f"{name} not deterministic"


def test_e2e_install_adapter_backs_up(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "CLAUDE.md").write_text("ORIGINAL CONTENT")
    r = subprocess.run(
        [_agentos_bin(), "install-adapter", "--cli", "claude",
         "--target", str(target), "--mode", "copy", "--backup"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    # Backup file should exist
    backups = list(target.glob("CLAUDE.md.bak.*"))
    assert backups, f"no backup file created; dir: {list(target.iterdir())}"
    assert backups[0].read_text() == "ORIGINAL CONTENT"
