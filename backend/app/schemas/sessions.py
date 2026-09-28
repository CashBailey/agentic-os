from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.common import ORMBase


class SessionEndIn(BaseModel):
    summary: str
    started_at: Optional[datetime] = None


class SessionSummaryRead(ORMBase):
    id: int
    project_id: Optional[int]
    summary: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime
