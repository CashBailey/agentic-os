"""Async DB session + sync engine for the worker."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings, sync_database_url


def _async_url(url: str) -> str:
    # SQLAlchemy's psycopg3 driver supports both sync and async via the
    # same +psycopg URL prefix; create_async_engine will pick the async
    # variant automatically.
    return url


_async_engine = create_async_engine(_async_url(settings.DATABASE_URL), future=True)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


def get_async_engine() -> Any:
    return _async_engine


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


# -- Sync engine (for the durable worker; SKIP LOCKED is easier sync) --
_sync_engine = create_engine(sync_database_url(), future=True)
SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    _sync_engine, expire_on_commit=False, class_=Session
)


def get_sync_engine() -> Any:
    return _sync_engine
