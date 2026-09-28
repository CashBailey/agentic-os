from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects import resolve_project_id
from app.db.session import get_session
from app.models.adapters import AdapterGeneration
from app.models.tasks import TaskRun
from app.schemas.adapters import AdapterGenerationRead
from app.services.audit import record as audit_record

router = APIRouter(prefix="/projects/{slug}/adapters", tags=["adapters"])


@router.get("", response_model=list[AdapterGenerationRead])
async def list_adapters(slug: str, session: AsyncSession = Depends(get_session)):
    pid = await resolve_project_id(slug, session)
    rows = (
        await session.execute(
            select(AdapterGeneration)
            .where(AdapterGeneration.project_id == pid)
            .order_by(AdapterGeneration.generated_at.desc())
        )
    ).scalars()
    return [AdapterGenerationRead.model_validate(a) for a in rows]


@router.post("/compile", status_code=202)
async def compile_adapters(slug: str, session: AsyncSession = Depends(get_session)):
    pid = await resolve_project_id(slug, session)
    task = TaskRun(project_id=pid, kind="adapter.compile", payload={"slug": slug})
    session.add(task)
    await session.flush()
    await audit_record(
        session,
        event_type="adapter.compile.queued",
        project_id=pid,
        payload={"task_id": task.id, "slug": slug},
    )
    await session.commit()
    await session.refresh(task)
    return {"task_id": task.id, "status": task.status}


@router.get("/{cli}/diff")
async def adapter_diff(
    slug: str,
    cli: str,
    target: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    await resolve_project_id(slug, session)
    # Diff computation is delegated to the CLI; this is a stub returning
    # the last generation summary.
    rows = (
        await session.execute(
            select(AdapterGeneration)
            .where(AdapterGeneration.cli == cli)
            .order_by(AdapterGeneration.generated_at.desc())
            .limit(1)
        )
    ).scalars().first()
    return {
        "cli": cli,
        "target": target,
        "last_generation": AdapterGenerationRead.model_validate(rows).model_dump()
        if rows
        else None,
        "diff": "",
    }
