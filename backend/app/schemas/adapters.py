from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.schemas.common import ORMBase


class AdapterGenerationRead(ORMBase):
    id: int
    project_id: Optional[int]
    cli: str
    generated_at: datetime
    source_hash: str
    output_hash: str
    files: list[dict[str, Any]]
