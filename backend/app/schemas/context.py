from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.common import ORMBase


class ContextDocumentRead(ORMBase):
    id: int
    project_id: Optional[int]
    scope: str
    category: str
    path: str
    content: str
    frontmatter: Optional[dict[str, Any]] = None
    content_hash: str
    created_at: datetime
    updated_at: datetime


class ContextDocumentUpdate(BaseModel):
    content: str
    frontmatter: Optional[dict[str, Any]] = None
