"""SSE event stream. Polls DB every 1s for new audit/approval/task/adapter events.

Event envelope: ``event: <type>\\ndata: <json>\\n\\n`` (sse-starlette handles formatting).
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.session import AsyncSessionLocal
from app.models.adapters import AdapterGeneration
from app.models.approvals import ApprovalRequest
from app.models.audit import AuditEvent
from app.models.projects import Project
from app.models.tasks import TaskRun

router = APIRouter(tags=["events"])


@router.get("/events")
async def events(
    project: str | None = Query(default=None),
    since: int | None = Query(default=None),
):
    async def gen() -> AsyncIterator[dict]:
        # Establish baseline cursors.
        cursors: dict[str, int] = {
            "audit": since or 0,
            "approval": 0,
            "task": 0,
            "adapter": 0,
        }
        pid: int | None = None
        async with AsyncSessionLocal() as s:
            if project:
                pid = (
                    await s.execute(select(Project.id).where(Project.slug == project))
                ).scalar_one_or_none()
            for table, key, attr in (
                (AuditEvent, "audit", AuditEvent.id),
                (ApprovalRequest, "approval", ApprovalRequest.id),
                (TaskRun, "task", TaskRun.id),
                (AdapterGeneration, "adapter", AdapterGeneration.id),
            ):
                stmt = select(attr).order_by(attr.desc()).limit(1)
                if pid is not None and hasattr(table, "project_id"):
                    stmt = stmt.where(table.project_id == pid)
                last = (await s.execute(stmt)).scalar_one_or_none()
                if last and key != "audit":
                    cursors[key] = last

        while True:
            try:
                async with AsyncSessionLocal() as s:
                    # audit
                    stmt = select(AuditEvent).where(AuditEvent.id > cursors["audit"]).order_by(AuditEvent.id)
                    if pid is not None:
                        stmt = stmt.where(AuditEvent.project_id == pid)
                    for row in (await s.execute(stmt)).scalars():
                        cursors["audit"] = row.id
                        yield {
                            "event": "audit",
                            "data": json.dumps(
                                {
                                    "id": row.id,
                                    "event_type": row.event_type,
                                    "actor": row.actor,
                                    "payload": row.payload,
                                    "occurred_at": row.occurred_at.isoformat(),
                                }
                            ),
                        }
                    # approvals (pending)
                    stmt = (
                        select(ApprovalRequest)
                        .where(ApprovalRequest.id > cursors["approval"], ApprovalRequest.status == "pending")
                        .order_by(ApprovalRequest.id)
                    )
                    for row in (await s.execute(stmt)).scalars():
                        cursors["approval"] = row.id
                        yield {
                            "event": "approval.pending",
                            "data": json.dumps({"id": row.id, "tool": row.tool, "action": row.action}),
                        }
                    # tasks
                    stmt = select(TaskRun).where(TaskRun.id > cursors["task"]).order_by(TaskRun.id)
                    for row in (await s.execute(stmt)).scalars():
                        cursors["task"] = row.id
                        yield {
                            "event": "task.status",
                            "data": json.dumps({"id": row.id, "kind": row.kind, "status": row.status}),
                        }
                    # adapters
                    stmt = select(AdapterGeneration).where(AdapterGeneration.id > cursors["adapter"]).order_by(AdapterGeneration.id)
                    for row in (await s.execute(stmt)).scalars():
                        cursors["adapter"] = row.id
                        yield {
                            "event": "adapter.generated",
                            "data": json.dumps({"id": row.id, "cli": row.cli}),
                        }
            except Exception as e:
                yield {"event": "error", "data": json.dumps({"error": str(e)})}
            await asyncio.sleep(1.0)

    return EventSourceResponse(gen())
