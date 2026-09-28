from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.schemas.common import HealthOut

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthOut)
async def healthz() -> HealthOut:
    return HealthOut(status="ok", version=settings.APP_VERSION)
