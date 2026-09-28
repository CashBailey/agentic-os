from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.audit import AuditEvent
from app.models.projects import Project
from app.schemas.audit import AuditEventRead, AuditPage

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditPage)
async def list_audit(
    project: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    cursor: int | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(AuditEvent)
    if project:
        pid = (await session.execute(select(Project.id).where(Project.slug == project))).scalar_one_or_none()
        if pid is not None:
            stmt = stmt.where(AuditEvent.project_id == pid)
    if since:
        stmt = stmt.where(AuditEvent.occurred_at >= since)
    if cursor:
        stmt = stmt.where(AuditEvent.id < cursor)
    stmt = stmt.order_by(AuditEvent.id.desc()).limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars())
    next_cursor = None
    if len(rows) > limit:
        next_cursor = rows[limit - 1].id
        rows = rows[:limit]
    return AuditPage(
        items=[AuditEventRead.model_validate(r) for r in rows],
        next_cursor=next_cursor,
    )
