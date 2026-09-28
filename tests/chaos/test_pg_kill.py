"""Chaos: kill the Postgres container mid-transaction.

Asserts:
    1. After ``docker kill agentos-db``, a fresh connection fails (and, when a
       backend HTTP service is bound to 127.0.0.1:8000, the next request
       surfaces an unhealthy response or connection error rather than a
       half-committed result).
    2. After ``docker start agentos-db`` and pg_isready, the database has no
       half-written row from the transaction that was in flight when Postgres
       died -- atomicity holds across the crash.

Requires: docker + the ``agentos-db`` container. Skips cleanly otherwise.
"""
from __future__ import annotations

import subprocess
import time
import uuid
from typing import Optional

import pytest

from .conftest import (
    backend_http_available,
    container_running,
    db_available,
    docker_available,
)

CONTAINER = "agentos-db"
PG_READY_TIMEOUT_S = 45


def _pg_isready() -> bool:
    r = subprocess.run(
        ["docker", "exec", CONTAINER, "pg_isready", "-U", "agentos", "-d", "agentos"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return r.returncode == 0


def _wait_pg_ready(timeout_s: int = PG_READY_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if container_running(CONTAINER) and _pg_isready():
            return True
        time.sleep(1.0)
    return False


def _start_container() -> None:
    subprocess.run(["docker", "start", CONTAINER], capture_output=True, text=True, timeout=30)


@pytest.fixture
def restore_pg():
    """Always try to bring the DB back up after the test, even on failure."""
    yield
    if not container_running(CONTAINER):
        _start_container()
        _wait_pg_ready()


def test_pg_kill_no_half_written_rows(restore_pg) -> None:
    ok, reason = docker_available()
    if not ok:
        pytest.skip(f"docker unavailable: {reason}")
    if not container_running(CONTAINER):
        pytest.skip(f"container {CONTAINER!r} is not running")
    ok, reason = db_available()
    if not ok:
        pytest.skip(f"db unavailable: {reason}")

    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError, SQLAlchemyError

    from app.config import sync_database_url

    marker = f"chaos-pgkill-{uuid.uuid4().hex[:12]}"
    eng = create_engine(sync_database_url(), future=True)

    # Begin a transaction, INSERT, then kill PG before commit.
    conn = eng.connect()
    trans = conn.begin()
    try:
        conn.execute(
            text(
                "INSERT INTO projects (slug, name, root_path) "
                "VALUES (:slug, :name, :root)"
            ),
            {"slug": marker, "name": marker, "root": f"/tmp/{marker}"},
        )
        # Do NOT commit. Kill PG now.
        kill = subprocess.run(
            ["docker", "kill", CONTAINER],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert kill.returncode == 0, f"docker kill failed: {kill.stderr}"
        # Attempt to commit; it should fail.
        with pytest.raises((OperationalError, SQLAlchemyError)):
            trans.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            eng.dispose()
        except Exception:
            pass

    # Fresh connection while PG is down should fail.
    down_eng = create_engine(sync_database_url(), future=True)
    with pytest.raises(Exception):
        with down_eng.connect() as c:
            c.execute(text("SELECT 1"))
    down_eng.dispose()

    # Best-effort: backend HTTP returns non-2xx / connection error.
    if backend_http_available("http://127.0.0.1:8000/health"):
        # Backend was up before; check it's now signalling unhealthy.
        import urllib.request

        unhealthy = False
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8000/health", timeout=2.0
            ) as resp:
                unhealthy = resp.status >= 500
        except Exception:
            unhealthy = True
        assert unhealthy, "backend reports healthy after PG was killed"

    # Bring PG back.
    _start_container()
    assert _wait_pg_ready(), "postgres did not become ready after restart"

    # Verify no half-written row.
    up_eng = create_engine(sync_database_url(), future=True)
    try:
        with up_eng.connect() as c:
            row: Optional[tuple] = c.execute(
                text("SELECT id FROM projects WHERE slug = :s"),
                {"s": marker},
            ).first()
        assert row is None, f"half-written row survived crash: slug={marker!r}"
    finally:
        up_eng.dispose()
