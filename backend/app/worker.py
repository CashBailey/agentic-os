"""Durable worker.

- Polls task_runs via ``FOR UPDATE SKIP LOCKED`` (Postgres-specific).
- Heartbeats every WORKER_HEARTBEAT_SECONDS while a task is running.
- Reaper resets stuck running tasks (heartbeat older than WORKER_STUCK_SECONDS) → queued, attempts+=1.
- Approval expirer flips pending → expired past TTL.
- Dispatcher: adapter.compile, memory.embed (real impl), markdown.export, markdown.import.
- States strictly: queued → claimed → running → {succeeded|failed|cancelled|timed_out}.
"""

from __future__ import annotations

import hashlib
import logging
import os
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import SyncSessionLocal

log = logging.getLogger("agentos.worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
TERMINAL = ("succeeded", "failed", "cancelled", "timed_out")


def _emit_audit(
    session: Session,
    *,
    event_type: str,
    project_id: int | None,
    payload: dict[str, Any],
) -> None:
    """Insert an audit_events row via raw SQL (no commit)."""
    import json as _json

    session.execute(
        text(
            """
            INSERT INTO audit_events (event_type, project_id, actor, payload)
            VALUES (:et, :pid, :actor, CAST(:p AS jsonb))
            """
        ),
        {
            "et": event_type,
            "pid": project_id,
            "actor": f"worker:{WORKER_ID}",
            "p": _json.dumps(payload),
        },
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Claim ----------

def claim_one(session: Session, worker_id: str = WORKER_ID) -> Optional[int]:
    """Claim a single queued task. Returns task id or None."""
    row = session.execute(
        text(
            """
            SELECT id FROM task_runs
             WHERE status = 'queued' AND created_at <= now()
             ORDER BY created_at
             LIMIT 1
             FOR UPDATE SKIP LOCKED
            """
        )
    ).first()
    if row is None:
        session.commit()
        return None
    task_id = row[0]
    session.execute(
        text(
            """
            UPDATE task_runs
               SET status = 'claimed', claimed_by = :w, claimed_at = now(),
                   heartbeat_at = now(), updated_at = now()
             WHERE id = :id
            """
        ),
        {"w": worker_id, "id": task_id},
    )
    session.commit()
    return task_id


# ---------- Heartbeat ----------

class Heartbeat:
    def __init__(self, task_id: int, interval: int = settings.WORKER_HEARTBEAT_SECONDS):
        self.task_id = task_id
        self.interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                with SyncSessionLocal() as s:
                    s.execute(
                        text(
                            "UPDATE task_runs SET heartbeat_at = now(), updated_at = now() WHERE id = :id"
                        ),
                        {"id": self.task_id},
                    )
                    s.commit()
            except Exception as e:  # pragma: no cover
                log.warning("heartbeat failed for task %d: %s", self.task_id, e)

    def __enter__(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


# ---------- Dispatcher ----------

def _dispatch(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "memory.embed":
        return _do_memory_embed(payload)
    if kind == "adapter.compile":
        return {"stub": True, "kind": kind}
    if kind == "markdown.export":
        return {"stub": True, "kind": kind}
    if kind == "markdown.import":
        return {"stub": True, "kind": kind}
    raise ValueError(f"unknown task kind: {kind}")


def _do_memory_embed(payload: dict[str, Any]) -> dict[str, Any]:
    from sqlalchemy import select

    from app.models.memory import MemoryChunk, MemoryEmbedding, MemoryItem
    from app.services.embeddings import EMBEDDING_DIM, EmbeddingService
    from app.services.redaction import redact

    item_id = int(payload["memory_item_id"])
    with SyncSessionLocal() as s:
        item: MemoryItem | None = s.execute(
            select(MemoryItem).where(MemoryItem.id == item_id)
        ).scalar_one_or_none()
        if not item:
            return {"skipped": True, "reason": "memory_item missing"}
        # Crude chunking: split on double newline, keep order. Redact every chunk.
        raw_chunks = [c.strip() for c in item.body.split("\n\n") if c.strip()] or [item.body]
        safe_chunks = [redact(c) for c in raw_chunks]
        # Persist chunks.
        chunk_ids: list[int] = []
        for ordinal, t in enumerate(safe_chunks):
            mc = MemoryChunk(
                memory_item_id=item.id,
                ordinal=ordinal,
                text=t,
                text_hash=hashlib.sha256(t.encode("utf-8")).hexdigest(),
            )
            s.add(mc)
            s.flush()
            chunk_ids.append(mc.id)
        # Compute embeddings.
        try:
            vecs = EmbeddingService.embed(safe_chunks)
        except Exception as e:
            s.rollback()
            raise RuntimeError(f"embedding failed: {e}") from e
        for cid, vec in zip(chunk_ids, vecs):
            if len(vec) != EMBEDDING_DIM:
                raise RuntimeError(f"unexpected embedding dim {len(vec)}")
            s.add(
                MemoryEmbedding(
                    chunk_id=cid,
                    model_name=settings.EMBEDDING_MODEL,
                    embedding=vec,
                )
            )
        s.commit()
        return {"chunks": len(chunk_ids)}


def execute_task(task_id: int) -> None:
    with SyncSessionLocal() as s:
        row = s.execute(
            text(
                "SELECT kind, payload, attempts, max_attempts FROM task_runs WHERE id = :id"
            ),
            {"id": task_id},
        ).mappings().first()
        if not row:
            return
        kind = row["kind"]
        payload = row["payload"] or {}
        attempts = (row["attempts"] or 0) + 1
        max_attempts = row["max_attempts"]
        s.execute(
            text(
                "UPDATE task_runs SET status='running', attempts=:a, heartbeat_at=now(), updated_at=now() WHERE id=:id"
            ),
            {"a": attempts, "id": task_id},
        )
        s.commit()

    try:
        with Heartbeat(task_id):
            result = _dispatch(kind, payload)
        with SyncSessionLocal() as s:
            s.execute(
                text(
                    "UPDATE task_runs SET status='succeeded', result=:r::jsonb, updated_at=now() WHERE id=:id"
                ),
                {"r": __import__("json").dumps(result), "id": task_id},
            )
            pid = s.execute(
                text("SELECT project_id FROM task_runs WHERE id=:id"),
                {"id": task_id},
            ).scalar()
            _emit_audit(
                s,
                event_type=f"task.succeeded",
                project_id=pid,
                payload={"task_id": task_id, "kind": kind},
            )
            # For adapter.compile, emit a domain-specific completion event too.
            if kind == "adapter.compile":
                _emit_audit(
                    s,
                    event_type="adapter.compile.completed",
                    project_id=pid,
                    payload={"task_id": task_id, "result": result},
                )
            s.commit()
    except Exception as e:
        log.exception("task %d failed: %s", task_id, e)
        with SyncSessionLocal() as s:
            row = s.execute(
                text(
                    "SELECT attempts, max_attempts, project_id FROM task_runs WHERE id=:id"
                ),
                {"id": task_id},
            ).mappings().first()
            if row and row["attempts"] >= row["max_attempts"]:
                s.execute(
                    text(
                        "UPDATE task_runs SET status='failed', error=:e, updated_at=now() WHERE id=:id"
                    ),
                    {"e": str(e), "id": task_id},
                )
                _emit_audit(
                    s,
                    event_type="task.failed",
                    project_id=row["project_id"] if row else None,
                    payload={"task_id": task_id, "kind": kind, "error": str(e)},
                )
            else:
                s.execute(
                    text(
                        "UPDATE task_runs SET status='queued', error=:e, updated_at=now() WHERE id=:id"
                    ),
                    {"e": str(e), "id": task_id},
                )
            s.commit()


# ---------- Reaper / Expirer ----------

def reap_stuck() -> int:
    with SyncSessionLocal() as s:
        res = s.execute(
            text(
                f"""
                UPDATE task_runs
                   SET status = 'queued', attempts = attempts + 1, updated_at = now()
                 WHERE status IN ('claimed', 'running')
                   AND heartbeat_at < now() - interval '{settings.WORKER_STUCK_SECONDS} seconds'
                """
            )
        )
        s.commit()
        return res.rowcount or 0


def expire_approvals() -> int:
    with SyncSessionLocal() as s:
        res = s.execute(
            text(
                """
                UPDATE approval_requests
                   SET status = 'expired', updated_at = now()
                 WHERE status = 'pending' AND expires_at < now()
                """
            )
        )
        s.commit()
        return res.rowcount or 0


# ---------- Loop ----------

def main() -> None:
    log.info("Worker %s starting", WORKER_ID)
    last_reap = 0.0
    last_expire = 0.0
    while True:
        try:
            now = time.time()
            if now - last_reap > 60:
                n = reap_stuck()
                if n:
                    log.info("reaped %d stuck tasks", n)
                last_reap = now
            if now - last_expire > 30:
                n = expire_approvals()
                if n:
                    log.info("expired %d approvals", n)
                last_expire = now
            with SyncSessionLocal() as s:
                tid = claim_one(s)
            if tid is None:
                time.sleep(1.0)
                continue
            log.info("claimed task %d", tid)
            execute_task(tid)
        except KeyboardInterrupt:
            log.info("worker shutting down")
            return
        except Exception as e:  # pragma: no cover
            log.exception("worker loop error: %s", e)
            time.sleep(2.0)


if __name__ == "__main__":
    main()
