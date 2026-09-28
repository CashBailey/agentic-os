from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class ApprovalCreate(BaseModel):
    # Either ``project_slug`` (preferred) or ``project_id`` must be provided.
    # Slug is resolved server-side so clients don't need to know IDs.
    project_slug: Optional[str] = None
    project_id: Optional[int] = None
    tool: str
    action: str
    raw_input: dict[str, Any]
    normalized: Optional[dict[str, Any]] = None
    risk: Optional[str] = None
    agent_reason: Optional[str] = None
    policy_reason: Optional[str] = None
    ttl_seconds: Optional[int] = None


class ApprovalRead(ORMBase):
    id: int
    project_id: Optional[int]
    tool: str
    action: str
    raw_input: dict[str, Any]
    risk: Optional[str]
    status: str
    expires_at: datetime
    created_at: datetime


class ApprovalDecideIn(BaseModel):
    decision: str  # 'approved' | 'denied'
    reason: Optional[str] = None


class ApprovalReleaseOut(BaseModel):
    release_token: uuid.UUID
    status: str


class ApprovalExecuteIn(BaseModel):
    release_token: uuid.UUID
    execution_result: dict[str, Any] = Field(default_factory=dict)
