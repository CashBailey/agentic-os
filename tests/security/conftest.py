"""Shared fixtures for security-layer tests.

Ensures the FastAPI app and async DB session are importable by injecting
``backend/`` into ``sys.path``. Tests that touch the DB will be skipped at
runtime if the Postgres backend is unreachable.
"""
from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

pytest_asyncio = pytest.importorskip("pytest_asyncio")
pytest.importorskip("httpx")

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


def _db_reachable() -> bool:
    """Best-effort sync probe of the configured Postgres URL."""
    try:
        from app.config import sync_database_url
        from sqlalchemy import create_engine, text
    except Exception:
        return False
    try:
        eng = create_engine(sync_database_url(), future=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_reachable() -> bool:
    return _db_reachable()


@pytest_asyncio.fixture
async def async_client() -> AsyncIterator:
    """An httpx AsyncClient bound to the in-process FastAPI app."""
    import httpx
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator:
    """Yield an AsyncSession against the live database."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session
