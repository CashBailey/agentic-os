from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMBase


class ProjectCreate(BaseModel):
    slug: str
    name: str
    root_path: str


class ProjectRead(ORMBase):
    id: int
    slug: str
    name: str
    root_path: str
    created_at: datetime
    updated_at: datetime
