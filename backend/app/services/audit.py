"""Audit event helper.

Centralises creation of ``AuditEvent`` rows so every write path emits a
uniform record. Use ``record`` for async (FastAPI request) contexts and
``record_sync`` for the worker.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


async def record(
    db: AsyncSession,
    *,
    event_type: str,
    project_id: int | None = None,
    actor: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    """Insert an audit event using an async session.

    Callers are responsible for committing — this only ``flush``es so the
    event is part of the surrounding transaction.
    """
    evt = AuditEvent(
        event_type=event_type,
        project_id=project_id,
        actor=actor or "system",
        payload=payload or {},
    )
    db.add(evt)
    await db.flush()
    return evt


def record_sync(
    db: Session,
    *,
    event_type: str,
    project_id: int | None = None,
    actor: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    """Insert an audit event using a sync session (worker path)."""
    evt = AuditEvent(
        event_type=event_type,
        project_id=project_id,
        actor=actor or "system",
        payload=payload or {},
    )
    db.add(evt)
    db.flush()
    return evt
