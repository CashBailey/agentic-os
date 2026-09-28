from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects import resolve_project_id
from app.config import settings
from app.db.session import get_session
from app.models.approvals import ApprovalDecision, ApprovalRequest
from app.schemas.approvals import (
    ApprovalCreate,
    ApprovalDecideIn,
    ApprovalExecuteIn,
    ApprovalRead,
    ApprovalReleaseOut,
)
from app.services.audit import record as audit_record

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _expires_at_aware(a: ApprovalRequest) -> datetime:
    exp = a.expires_at
    return exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)


@router.get("", response_model=list[ApprovalRead])
async def list_approvals(
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    rows = (await session.execute(stmt)).scalars()
    return [ApprovalRead.model_validate(a) for a in rows]


@router.post("", response_model=ApprovalRead, status_code=201)
async def create_approval(
    body: ApprovalCreate, session: AsyncSession = Depends(get_session)
):
    # Resolve project: prefer slug (rejects unknown 404); fall back to id.
    pid: int | None = None
    if body.project_slug:
        pid = await resolve_project_id(body.project_slug, session)
    elif body.project_id is not None:
        pid = body.project_id
    # If neither provided, leave NULL (approvals can be global in principle,
    # but the test_approval_project_resolution.py contract says missing slug
    # → 422; we enforce that here by requiring at least one identifier).
    if pid is None:
        raise HTTPException(
            status_code=422,
            detail="project_slug or project_id is required",
        )

    ttl = body.ttl_seconds or settings.APPROVAL_TTL_SECONDS
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    a = ApprovalRequest(
        project_id=pid,
        tool=body.tool,
        action=body.action,
        raw_input=body.raw_input,
        normalized=body.normalized,
        risk=body.risk,
        agent_reason=body.agent_reason,
        policy_reason=body.policy_reason,
        expires_at=expires_at,
    )
    session.add(a)
    await session.flush()
    await audit_record(
        session,
        event_type="approval.requested",
        project_id=pid,
        payload={"approval_id": a.id, "tool": a.tool, "action": a.action, "risk": a.risk},
    )
    await session.commit()
    await session.refresh(a)
    return ApprovalRead.model_validate(a)


@router.post("/{approval_id}/decide", response_model=ApprovalRead)
async def decide(
    approval_id: int,
    body: ApprovalDecideIn,
    session: AsyncSession = Depends(get_session),
):
    if body.decision not in ("approved", "denied"):
        raise HTTPException(400, "decision must be approved|denied")
    a = (
        await session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "approval not found")
    if a.status not in ("pending", "requested"):
        raise HTTPException(409, f"cannot decide approval in status={a.status}")
    if datetime.now(timezone.utc) > _expires_at_aware(a):
        a.status = "expired"
        await audit_record(
            session,
            event_type="approval.expired",
            project_id=a.project_id,
            payload={"approval_id": a.id},
        )
        await session.commit()
        raise HTTPException(410, "approval expired")
    session.add(
        ApprovalDecision(
            approval_request_id=a.id, decision=body.decision, reason=body.reason
        )
    )
    a.status = body.decision
    await audit_record(
        session,
        event_type="approval.decided",
        project_id=a.project_id,
        payload={"approval_id": a.id, "decision": body.decision, "reason": body.reason},
    )
    await session.commit()
    await session.refresh(a)
    return ApprovalRead.model_validate(a)


@router.post("/{approval_id}/release", response_model=ApprovalReleaseOut)
async def release(
    approval_id: int, session: AsyncSession = Depends(get_session)
):
    a = (
        await session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "approval not found")
    if a.status != "approved":
        raise HTTPException(409, f"approval not in approved state (status={a.status})")
    if datetime.now(timezone.utc) >= _expires_at_aware(a):
        a.status = "expired"
        await audit_record(
            session,
            event_type="approval.expired",
            project_id=a.project_id,
            payload={"approval_id": a.id},
        )
        await session.commit()
        raise HTTPException(410, "approval expired")
    a.status = "released"
    await audit_record(
        session,
        event_type="approval.released",
        project_id=a.project_id,
        payload={"approval_id": a.id, "release_token": str(a.release_token)},
    )
    await session.commit()
    return ApprovalReleaseOut(release_token=a.release_token, status=a.status)


@router.post("/{approval_id}/execute", response_model=ApprovalRead)
async def execute_approval(
    approval_id: int,
    body: ApprovalExecuteIn,
    session: AsyncSession = Depends(get_session),
):
    a = (
        await session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "approval not found")
    if a.status != "released":
        raise HTTPException(
            409, f"approval not in released state (status={a.status})"
        )
    if str(a.release_token) != str(body.release_token):
        raise HTTPException(400, "release_token mismatch")
    if datetime.now(timezone.utc) >= _expires_at_aware(a):
        a.status = "expired"
        await audit_record(
            session,
            event_type="approval.expired",
            project_id=a.project_id,
            payload={"approval_id": a.id},
        )
        await session.commit()
        raise HTTPException(410, "approval expired")

    # Patch the most-recent decision row with the execution_result.
    most_recent = (
        await session.execute(
            select(ApprovalDecision)
            .where(ApprovalDecision.approval_request_id == a.id)
            .order_by(ApprovalDecision.decided_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if most_recent is not None:
        most_recent.execution_result = body.execution_result

    a.status = "executed"
    a.updated_at = datetime.now(timezone.utc)
    await audit_record(
        session,
        event_type="approval.executed",
        project_id=a.project_id,
        payload={"approval_id": a.id, "execution_result": body.execution_result},
    )
    await session.commit()
    await session.refresh(a)
    return ApprovalRead.model_validate(a)
