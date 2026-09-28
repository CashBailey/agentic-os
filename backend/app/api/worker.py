from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.tasks import TaskRun
from app.schemas.tasks import TaskCreate, TaskRead
from app.services.audit import record as audit_record

router = APIRouter(prefix="/worker/tasks", tags=["worker"])


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(TaskRun).order_by(TaskRun.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(TaskRun.status == status)
    rows = (await session.execute(stmt)).scalars()
    return [TaskRead.model_validate(t) for t in rows]


@router.post("", response_model=TaskRead, status_code=201)
async def enqueue_task(
    body: TaskCreate, session: AsyncSession = Depends(get_session)
):
    t = TaskRun(
        project_id=body.project_id,
        kind=body.kind,
        payload=body.payload,
        max_attempts=body.max_attempts,
        timeout_seconds=body.timeout_seconds,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return TaskRead.model_validate(t)


@router.post("/{task_id}/cancel", response_model=TaskRead)
async def cancel_task(task_id: int, session: AsyncSession = Depends(get_session)):
    t = (await session.execute(select(TaskRun).where(TaskRun.id == task_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "task not found")
    if t.status in ("succeeded", "failed", "cancelled", "timed_out"):
        raise HTTPException(409, f"task in terminal status={t.status}")
    t.status = "cancelled"
    await audit_record(
        session,
        event_type="task.cancelled",
        project_id=t.project_id,
        payload={"task_id": t.id, "kind": t.kind},
    )
    await session.commit()
    await session.refresh(t)
    return TaskRead.model_validate(t)
