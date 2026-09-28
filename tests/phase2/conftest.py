"""Shared fixtures for phase 2 tests."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_OS = REPO_ROOT / "agent-os"

# Ensure the project root is importable so the in-repo agentos_cli package is
# used (some CI/dev setups put other agentos shims on sys.path).
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture()
def real_agent_os() -> Path:
    """The real agent-os/ tree (read-only use; do not write into it)."""
    assert AGENT_OS.is_dir(), f"missing {AGENT_OS}"
    return AGENT_OS


@pytest.fixture()
def tmp_agent_os(tmp_path: Path) -> Path:
    """A throwaway copy of the agent-os/ tree under tmp_path."""
    dst = tmp_path / "agent-os"
    shutil.copytree(AGENT_OS, dst)
    # Wipe any pre-existing generated/ so tests start clean.
    gen = dst / "generated"
    if gen.exists():
        shutil.rmtree(gen)
    gen.mkdir(parents=True, exist_ok=True)
    return dst
