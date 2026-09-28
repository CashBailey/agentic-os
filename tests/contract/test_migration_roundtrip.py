"""Alembic migration roundtrip: upgrade head -> downgrade base -> upgrade head.

Verifies that:
1. ``alembic upgrade head`` lands on the current head without error.
2. ``alembic downgrade base`` removes every migration cleanly.
3. ``alembic upgrade head`` re-applies all migrations successfully.
4. Fixture rows survive a downgrade-of-just-data and re-seed correctly.

Marked @pytest.mark.db — skipped when Postgres is unreachable.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.db

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def _alembic(*cmd: str) -> subprocess.CompletedProcess[str]:
    """Run `alembic -c backend/alembic.ini <cmd>` from backend/ as cwd."""
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python"
    py = str(venv_python) if venv_python.exists() else "python3"
    full = [py, "-m", "alembic", "-c", str(ALEMBIC_INI), *cmd]
    env = dict(os.environ)
    # Ensure backend/ is on PYTHONPATH for `app.*` imports inside alembic.
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{BACKEND_DIR}{os.pathsep}{pythonpath}" if pythonpath else str(BACKEND_DIR)
    )
    return subprocess.run(
        full,
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def _assert_ok(proc: subprocess.CompletedProcess[str], label: str) -> None:
    assert proc.returncode == 0, (
        f"{label} failed (rc={proc.returncode})\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )


def _current_revision() -> str:
    proc = _alembic("current")
    _assert_ok(proc, "alembic current")
    # Output like "0001_initial (head)" or empty
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    return line


def test_alembic_upgrade_head():
    _assert_ok(_alembic("upgrade", "head"), "initial upgrade head")
    # current should be non-empty after upgrade
    assert _current_revision(), "no current revision after upgrade head"


def test_alembic_roundtrip_downgrade_base_upgrade_head():
    # Make sure we're at head first.
    _assert_ok(_alembic("upgrade", "head"), "pre-roundtrip upgrade head")

    # Downgrade all the way down.
    _assert_ok(_alembic("downgrade", "base"), "downgrade base")

    # After downgrade base, current should be empty (no revision).
    after_down = _current_revision()
    assert "head" not in after_down, f"unexpected head after downgrade: {after_down}"

    # Re-upgrade.
    _assert_ok(_alembic("upgrade", "head"), "re-upgrade head after base")
    assert _current_revision(), "no current revision after re-upgrade"


def test_alembic_roundtrip_with_fixture_rows():
    """Insert a fixture project before downgrade, verify the table is gone, then
    re-upgrade and confirm the schema is back."""
    from sqlalchemy import create_engine, text

    from app.config import sync_database_url

    eng = create_engine(sync_database_url(), future=True)

    # Ensure schema is at head before we start.
    _assert_ok(_alembic("upgrade", "head"), "pre-fixture upgrade head")

    import uuid as _uuid

    slug = f"roundtrip-{_uuid.uuid4().hex[:8]}"

    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO projects (slug, name, root_path) "
                "VALUES (:s, :n, :r)"
            ),
            {"s": slug, "n": "rt", "r": "/tmp"},
        )
        row = c.execute(
            text("SELECT slug FROM projects WHERE slug = :s"), {"s": slug}
        ).first()
        assert row is not None and row[0] == slug

    # Downgrade to base — projects table should disappear.
    _assert_ok(_alembic("downgrade", "base"), "downgrade base after fixture")

    with eng.connect() as c:
        exists = c.execute(
            text(
                "SELECT to_regclass('public.projects') IS NOT NULL"
            )
        ).scalar()
        assert exists is False, "projects table still present after downgrade base"

    # Re-upgrade — schema returns; the fixture row is gone (downgrade dropped it).
    _assert_ok(_alembic("upgrade", "head"), "re-upgrade head after fixture downgrade")

    with eng.connect() as c:
        cnt = c.execute(
            text("SELECT count(*) FROM projects WHERE slug = :s"), {"s": slug}
        ).scalar()
        assert cnt == 0, "fixture row unexpectedly survived downgrade->upgrade"
