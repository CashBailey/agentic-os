from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.common import ORMBase


class TaskCreate(BaseModel):
    kind: str
    payload: dict[str, Any] = {}
    project_id: Optional[int] = None
    max_attempts: int = 3
    timeout_seconds: int = 600


class TaskRead(ORMBase):
    id: int
    project_id: Optional[int]
    kind: str
    status: str
    payload: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int
    max_attempts: int
    timeout_seconds: int
    created_at: datetime
    updated_at: datetime
