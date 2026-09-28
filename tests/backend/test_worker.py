"""Worker concurrency: 5 threads racing on 5 tasks → each task claimed exactly once."""

from __future__ import annotations

import threading

import pytest


@pytest.mark.db
def test_skip_locked_claim_no_duplicates():
    from app.db.session import SyncSessionLocal
    from app.models.tasks import TaskRun
    from app.worker import claim_one

    # Seed 5 tasks.
    seeded: list[int] = []
    with SyncSessionLocal() as s:
        for i in range(5):
            t = TaskRun(kind="memory.embed", payload={"i": i})
            s.add(t)
            s.flush()
            seeded.append(t.id)
        s.commit()

    claimed: list[int] = []
    lock = threading.Lock()

    def worker(name: str):
        for _ in range(5):
            with SyncSessionLocal() as s:
                tid = claim_one(s, worker_id=name)
            if tid is not None:
                with lock:
                    claimed.append(tid)

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    # Each seeded task claimed at most once.
    assert set(claimed) >= set(seeded), f"missed tasks: seeded={seeded} claimed={claimed}"
    assert len(claimed) == len(set(claimed)), f"duplicate claims: {claimed}"

    # Cleanup: mark claimed tasks as cancelled so they don't linger.
    with SyncSessionLocal() as s:
        for tid in seeded:
            s.execute(
                __import__("sqlalchemy").text(
                    "UPDATE task_runs SET status='cancelled' WHERE id=:id"
                ),
                {"id": tid},
            )
        s.commit()
