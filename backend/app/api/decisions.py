from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects import resolve_project_id
from app.db.session import get_session
from app.models.decisions import Decision
from app.schemas.decisions import DecisionCreate, DecisionRead

router = APIRouter(prefix="/projects/{slug}/decisions", tags=["decisions"])


@router.get("", response_model=list[DecisionRead])
async def list_decisions(slug: str, session: AsyncSession = Depends(get_session)):
    pid = await resolve_project_id(slug, session)
    rows = (
        await session.execute(
            select(Decision).where(Decision.project_id == pid).order_by(Decision.decided_at.desc())
        )
    ).scalars()
    return [DecisionRead.model_validate(d) for d in rows]


@router.post("", response_model=DecisionRead, status_code=201)
async def create_decision(
    slug: str, body: DecisionCreate, session: AsyncSession = Depends(get_session)
):
    pid = await resolve_project_id(slug, session)
    d = Decision(project_id=pid, title=body.title, body=body.body)
    session.add(d)
    await session.commit()
    await session.refresh(d)
    return DecisionRead.model_validate(d)
