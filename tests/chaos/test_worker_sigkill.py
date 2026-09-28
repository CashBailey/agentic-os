"""Chaos: SIGKILL a worker mid-running task; assert another worker reclaims it.

We simulate the SIGKILL outcome at the database level: a row is inserted in
``running`` state with a stale ``heartbeat_at`` (older than the stuck-task
window). The reaper -- whether called in-process via ``app.worker.reap_stuck``
or from a peer worker loop -- must reset the row to ``queued`` and increment
``attempts``.

Doing it this way avoids the flakiness of timing a real OS-level SIGKILL
against the dispatcher loop while still proving the contract: a worker that
disappears mid-task does not block the task forever.

Requires: Postgres reachable. Skips cleanly otherwise.
"""
from __future__ import annotations

import json
import uuid

import pytest

from .conftest import db_available


def test_killed_worker_task_is_reclaimed() -> None:
    ok, reason = db_available()
    if not ok:
        pytest.skip(f"db unavailable: {reason}")

    from sqlalchemy import text

    from app.db.session import SyncSessionLocal
    from app.worker import reap_stuck

    marker = f"chaos-sigkill-{uuid.uuid4().hex[:12]}"
    payload = {"marker": marker}

    # Insert a task that looks like it was claimed by a now-dead worker.
    # heartbeat_at is 1 hour in the past, so it's stale under any reasonable
    # WORKER_STUCK_SECONDS setting (default 90s).
    with SyncSessionLocal() as s:
        row = s.execute(
            text(
                """
                INSERT INTO task_runs
                    (kind, status, payload, claimed_by, claimed_at,
                     heartbeat_at, attempts, max_attempts, timeout_seconds)
                VALUES
                    ('memory.embed', 'running', CAST(:p AS jsonb),
                     :worker, now() - interval '1 hour',
                     now() - interval '1 hour', 0, 3, 600)
                RETURNING id
                """
            ),
            {"p": json.dumps(payload), "worker": "dead-worker-x"},
        ).first()
        assert row is not None
        task_id = int(row[0])
        s.commit()

    try:
        n = reap_stuck()
        assert n >= 1, f"reap_stuck returned {n}; expected >= 1"

        with SyncSessionLocal() as s:
            after = s.execute(
                text(
                    "SELECT status, attempts FROM task_runs WHERE id = :i"
                ),
                {"i": task_id},
            ).first()
        assert after is not None, "task row vanished after reap"
        status, attempts = after[0], int(after[1])
        assert status == "queued", f"expected status='queued', got {status!r}"
        assert attempts == 1, f"expected attempts=1, got {attempts}"
    finally:
        with SyncSessionLocal() as s:
            s.execute(text("DELETE FROM task_runs WHERE id = :i"), {"i": task_id})
            s.commit()
