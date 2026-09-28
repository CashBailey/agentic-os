"""Hypothesis property test: FOR UPDATE SKIP LOCKED never double-claims under
concurrent stress.

Strategy:
- Seed N queued task_runs in the DB.
- Launch K worker threads, each repeatedly invoking ``claim_one`` from
  backend/app/worker.py until the queue is drained.
- Collect every (claimed_task_id, worker_id) tuple.
- INVARIANT: every task_id appears at most once across all workers.

Marked @pytest.mark.db — skipped if Postgres is unreachable.
"""
from __future__ import annotations

import os
import threading
import uuid
from typing import List, Tuple

import pytest

# Hypothesis is required for this property test.
hyp = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings as hsettings, strategies as st

pytestmark = pytest.mark.db


# ------------- helpers -------------

def _sync_session():
    from app.db.session import SyncSessionLocal
    return SyncSessionLocal()


def _seed_tasks(n: int) -> list[int]:
    """Insert n queued task_runs and return their ids."""
    from sqlalchemy import text

    tag = f"prop-{uuid.uuid4().hex[:8]}"
    ids: list[int] = []
    with _sync_session() as s:
        for _ in range(n):
            row = s.execute(
                text(
                    """
                    INSERT INTO task_runs (project_id, kind, status, payload,
                                           max_attempts, timeout_seconds, attempts)
                    VALUES (NULL, :kind, 'queued', CAST('{}' AS jsonb), 1, 60, 0)
                    RETURNING id
                    """
                ),
                {"kind": f"property.noop.{tag}"},
            ).first()
            assert row is not None
            ids.append(int(row[0]))
        s.commit()
    return ids


def _cleanup(ids: list[int]) -> None:
    if not ids:
        return
    from sqlalchemy import text

    with _sync_session() as s:
        s.execute(text("DELETE FROM task_runs WHERE id = ANY(:ids)"), {"ids": ids})
        s.commit()


def _drain(worker_id: str, out: list[Tuple[int, str]], stop_after: int) -> None:
    """Call claim_one repeatedly until we've claimed `stop_after` or queue empty."""
    from app.worker import claim_one

    claimed_local = 0
    while claimed_local < stop_after:
        with _sync_session() as s:
            tid = claim_one(s, worker_id=worker_id)
        if tid is None:
            break
        out.append((tid, worker_id))
        claimed_local += 1


# ------------- property -------------

@hsettings(
    max_examples=int(os.environ.get("WORKER_PROPERTY_MAX_EXAMPLES", "5")),
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    n_tasks=st.integers(min_value=2, max_value=20),
    n_workers=st.integers(min_value=2, max_value=6),
)
def test_skip_locked_never_double_claims(n_tasks, n_workers):
    """Under concurrent claim_one calls, no task_id is ever claimed twice."""
    ids = _seed_tasks(n_tasks)
    try:
        results: List[Tuple[int, str]] = []
        lock = threading.Lock()

        def runner(wid: str):
            local: list[Tuple[int, str]] = []
            _drain(wid, local, stop_after=n_tasks)
            with lock:
                results.extend(local)

        threads = [
            threading.Thread(target=runner, args=(f"worker-{i}-{uuid.uuid4().hex[:6]}",))
            for i in range(n_workers)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        claimed_ids = [tid for tid, _ in results]
        # INVARIANT 1: no duplicate claims.
        assert len(claimed_ids) == len(set(claimed_ids)), (
            f"Double-claim detected: {sorted(claimed_ids)}"
        )

        # INVARIANT 2: all claimed ids belong to our seeded set
        # (others may exist in the DB from prior runs; we only seeded `ids`).
        assert set(claimed_ids).issubset(set(ids))

        # INVARIANT 3: at most n_tasks claims (one per task we seeded).
        assert len(claimed_ids) <= n_tasks
    finally:
        _cleanup(ids)


def test_claim_one_returns_none_on_empty_queue():
    """Sanity: with no queued rows in our seed set, drain returns nothing.

    We can't guarantee the DB has zero queued rows globally, but we can
    verify that after we claim all seeded rows, none of OUR ids remain
    claimable by a fresh call.
    """
    ids = _seed_tasks(3)
    try:
        from app.worker import claim_one

        claimed: list[int] = []
        # Drain everything (may include other rows in DB — fine).
        while True:
            with _sync_session() as s:
                tid = claim_one(s, worker_id="solo-worker")
            if tid is None:
                break
            claimed.append(tid)
            if len(claimed) > 1000:
                break  # safety against unrelated huge queues

        # Every seeded id must have been claimed exactly once.
        for sid in ids:
            assert claimed.count(sid) == 1, f"id {sid} claim count = {claimed.count(sid)}"
    finally:
        _cleanup(ids)
