from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.common import ORMBase


class DecisionCreate(BaseModel):
    title: str
    body: str


class DecisionRead(ORMBase):
    id: int
    project_id: Optional[int]
    title: str
    body: str
    decided_at: datetime
    created_at: datetime
