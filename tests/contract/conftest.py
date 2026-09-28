"""Conftest for tests/contract/.

Provides async client fixture and DB-skip behavior matching tests/backend/.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
_BACKEND = _REPO / "backend"
for p in (_BACKEND, _REPO):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)


def _db_reachable() -> bool:
    if os.environ.get("SKIP_DB_TESTS"):
        return False
    try:
        from sqlalchemy import create_engine, text
        from app.config import sync_database_url

        eng = create_engine(sync_database_url(), future=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


_DB_OK = _db_reachable()


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    if _DB_OK:
        return
    skip_db = pytest.mark.skip(reason="DB not reachable / SKIP_DB_TESTS set")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip_db)


@pytest.fixture
def app():
    from app.main import create_app
    return create_app()


@pytest.fixture
async def client(app):
    import httpx
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
