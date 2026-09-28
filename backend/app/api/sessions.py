from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects import resolve_project_id
from app.db.session import get_session
from app.models.sessions import SessionSummary
from app.schemas.sessions import SessionEndIn, SessionSummaryRead
from app.services.audit import record as audit_record

router = APIRouter(prefix="/projects/{slug}/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummaryRead])
async def list_sessions(slug: str, session: AsyncSession = Depends(get_session)):
    pid = await resolve_project_id(slug, session)
    rows = (
        await session.execute(
            select(SessionSummary)
            .where(SessionSummary.project_id == pid)
            .order_by(SessionSummary.created_at.desc())
        )
    ).scalars()
    return [SessionSummaryRead.model_validate(s) for s in rows]


@router.post("/end", response_model=SessionSummaryRead, status_code=201)
async def end_session(
    slug: str, body: SessionEndIn, session: AsyncSession = Depends(get_session)
):
    pid = await resolve_project_id(slug, session)
    s = SessionSummary(
        project_id=pid,
        summary=body.summary,
        started_at=body.started_at,
        ended_at=datetime.now(timezone.utc),
    )
    session.add(s)
    await session.flush()
    await audit_record(
        session,
        event_type="session.ended",
        project_id=pid,
        payload={"session_id": s.id},
    )
    await session.commit()
    await session.refresh(s)
    return SessionSummaryRead.model_validate(s)
