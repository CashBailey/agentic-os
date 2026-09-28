from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.common import ORMBase


class MemoryItemCreate(BaseModel):
    kind: str
    title: Optional[str] = None
    body: str
    tags: list[str] = []


class MemoryItemRead(ORMBase):
    id: int
    project_id: Optional[int]
    kind: str
    title: Optional[str]
    body: str
    tags: list[str]
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class SemanticSearchIn(BaseModel):
    query: str
    top_k: int = 10


class SemanticSearchHit(BaseModel):
    memory_item_id: int
    chunk_id: int
    score: float
    text: str


class SemanticSearchOut(BaseModel):
    hits: list[SemanticSearchHit]
