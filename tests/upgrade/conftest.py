"""Shared helpers for upgrade/downgrade migration tests.

Wraps the backend's own alembic venv so tests don't depend on a globally
installed alembic. All commands run with cwd=backend so the relative
``alembic.ini`` and ``alembic/`` script_location resolve correctly.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
ALEMBIC_BIN = BACKEND_DIR / ".venv" / "bin" / "alembic"

# Make the backend package importable for tests that touch app.* directly.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def alembic_available() -> Tuple[bool, str]:
    if not ALEMBIC_BIN.exists():
        return False, f"alembic not found at {ALEMBIC_BIN}"
    return True, ""


def _clean_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def run_alembic(*args: str, check: bool = True, timeout: float = 120.0) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [str(ALEMBIC_BIN), *args],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_clean_env(),
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"alembic {' '.join(args)} failed (rc={proc.returncode})\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def current_revision() -> Optional[str]:
    """Return the current revision id (without ' (head)' suffix), or None if base."""
    r = run_alembic("current", check=True, timeout=30.0)
    out = (r.stdout or "").strip()
    if not out:
        return None
    # Examples:
    #   "0001_initial (head)"
    #   "INFO ...\n0001_initial (head)"
    last = out.splitlines()[-1].strip()
    m = re.match(r"^([A-Za-z0-9_]+)", last)
    return m.group(1) if m else None


def history_revisions() -> List[str]:
    """Return revision ids in head -> base order."""
    r = run_alembic("history", "--verbose", check=True, timeout=30.0)
    revs: List[str] = []
    for line in (r.stdout or "").splitlines():
        # Lines look like: "Rev: 0001_initial (head)"
        m = re.match(r"^Rev:\s+([A-Za-z0-9_]+)", line.strip())
        if m:
            revs.append(m.group(1))
    return revs


def db_available() -> Tuple[bool, str]:
    if os.environ.get("SKIP_DB_TESTS"):
        return False, "SKIP_DB_TESTS is set"
    try:
        from sqlalchemy import create_engine, text

        from app.config import sync_database_url
    except Exception as e:  # pragma: no cover
        return False, f"backend not importable: {e!r}"
    try:
        eng = create_engine(sync_database_url(), future=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return True, ""
    except Exception as e:
        return False, f"postgres not reachable: {e!r}"


@pytest.fixture(scope="module", autouse=True)
def _require_alembic_and_db():
    ok, reason = alembic_available()
    if not ok:
        pytest.skip(f"alembic unavailable: {reason}")
    ok, reason = db_available()
    if not ok:
        pytest.skip(f"db unavailable: {reason}")
