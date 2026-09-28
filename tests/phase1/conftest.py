"""Shared fixtures for phase1 tests."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_OS_ROOT = REPO_ROOT / "agent-os"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def agent_os_root() -> Path:
    return AGENT_OS_ROOT
