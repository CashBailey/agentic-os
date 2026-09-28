from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.common import ORMBase


class AuditEventRead(ORMBase):
    id: int
    project_id: Optional[int]
    event_type: str
    actor: Optional[str]
    payload: dict[str, Any]
    occurred_at: datetime


class AuditPage(BaseModel):
    items: list[AuditEventRead]
    next_cursor: Optional[int] = None
