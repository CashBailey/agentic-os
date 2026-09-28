from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException

from app.api.projects import resolve_project_id
from app.config import settings
from app.db.session import get_session
from app.schemas.policies import (
    PolicyFileRead,
    PolicySimulateIn,
    PolicySimulateOut,
    PolicyUpdateIn,
)
from app.services.policy_eval import (
    evaluate_file,
    evaluate_mcp,
    evaluate_shell,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/projects/{slug}/policies", tags=["policies"])

POLICY_FILES = {
    "shell": "shell-policy.yaml",
    "file": "file-policy.yaml",
    "mcp": "mcp-policy.yaml",
    "approval": "approval-policy.yaml",
}


def _policy_path(kind: str) -> Path:
    if kind not in POLICY_FILES:
        raise HTTPException(404, f"unknown policy kind: {kind}")
    return Path(settings.AGENT_OS_ROOT) / "policies" / POLICY_FILES[kind]


def _read_policy(kind: str) -> PolicyFileRead:
    p = _policy_path(kind)
    if not p.exists():
        return PolicyFileRead(kind=kind, path=str(p), content="", parsed_ok=False, parse_error="missing")
    content = p.read_text(encoding="utf-8")
    try:
        yaml.safe_load(content)
        return PolicyFileRead(kind=kind, path=str(p), content=content, parsed_ok=True)
    except Exception as e:
        return PolicyFileRead(kind=kind, path=str(p), content=content, parsed_ok=False, parse_error=str(e))


@router.get("", response_model=list[PolicyFileRead])
async def list_policies(slug: str, session: AsyncSession = Depends(get_session)):
    await resolve_project_id(slug, session)
    return [_read_policy(k) for k in POLICY_FILES]


@router.put("/{kind}", response_model=PolicyFileRead)
async def update_policy(
    slug: str,
    kind: str,
    body: PolicyUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    await resolve_project_id(slug, session)
    try:
        yaml.safe_load(body.content)
    except Exception as e:
        raise HTTPException(400, f"YAML parse error: {e}")
    p = _policy_path(kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.content, encoding="utf-8")
    return _read_policy(kind)


@router.post("/simulate", response_model=PolicySimulateOut)
async def simulate(
    slug: str,
    body: PolicySimulateIn,
    session: AsyncSession = Depends(get_session),
):
    await resolve_project_id(slug, session)
    # Aggregate policies from disk.
    pols: dict = {}
    for kind in POLICY_FILES:
        p = _policy_path(kind)
        if p.exists():
            try:
                pols.update(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
            except Exception:
                pass
    if body.action == "shell":
        res = evaluate_shell([body.tool, *body.args], pols)
    elif body.action == "file_write" and body.path:
        res = evaluate_file(body.path, pols)
    elif body.action == "mcp_call":
        res = evaluate_mcp(body.tool, "write", pols)
    else:
        res = {"decision": "prompt", "matched_rule": None}
    return PolicySimulateOut(**res)
