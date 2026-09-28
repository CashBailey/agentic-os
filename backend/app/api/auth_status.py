from __future__ import annotations

from fastapi import APIRouter

from app.services.auth_status import get_auth_status

router = APIRouter(tags=["auth"])


@router.get("/auth-status")
async def auth_status() -> dict:
    return {"clis": get_auth_status()}
