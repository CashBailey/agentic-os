"""T-SEC-REDACT — fuzz 100 secret-shaped values through the memory API.

Asserts that no plaintext secret survives in MemoryItem.body or
MemoryChunk.text rows for the test project.
"""
from __future__ import annotations

import random
import re
import string
import uuid

import pytest

pytestmark = [pytest.mark.security, pytest.mark.asyncio]


def _gen_aws() -> str:
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
    return f"AKIA{body}"


def _gen_ghp() -> str:
    body = "".join(random.choices(string.ascii_letters + string.digits, k=36))
    return f"ghp_{body}"


def _gen_openai() -> str:
    body = "".join(random.choices(string.ascii_letters + string.digits, k=48))
    return f"sk-{body}"


def _make_secrets(n: int = 100) -> list[str]:
    rng = random.Random(0xC0FFEE)
    saved = random.getstate()
    random.seed(0xC0FFEE)
    try:
        out: list[str] = []
        for i in range(n):
            choice = i % 3
            if choice == 0:
                out.append(_gen_aws())
            elif choice == 1:
                out.append(_gen_ghp())
            else:
                out.append(_gen_openai())
        return out
    finally:
        random.setstate(saved)


SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


async def test_redaction_fuzz(db_reachable, async_client, db_session):
    if not db_reachable:
        pytest.skip("Postgres backend not reachable")

    from sqlalchemy import select

    from app.models.memory import MemoryChunk, MemoryItem
    from app.models.projects import Project

    slug = f"sec-redact-{uuid.uuid4().hex[:8]}"

    # Create project.
    resp = await async_client.post(
        "/projects",
        json={"slug": slug, "name": "sec-redact", "root_path": "/tmp"},
    )
    assert resp.status_code in (200, 201), resp.text

    secrets = _make_secrets(100)
    for i, sec in enumerate(secrets):
        body = f"context line {i}: see token {sec} thanks"
        r = await async_client.post(
            f"/projects/{slug}/memory",
            json={"kind": "note", "title": f"t{i}", "body": body, "tags": []},
        )
        assert r.status_code in (200, 201), r.text

    # Resolve project id.
    pid = (
        await db_session.execute(select(Project.id).where(Project.slug == slug))
    ).scalar_one()

    # Pull every body and chunk text for this project.
    rows = (
        await db_session.execute(
            select(MemoryItem.body).where(MemoryItem.project_id == pid)
        )
    ).scalars().all()
    chunk_rows = (
        await db_session.execute(
            select(MemoryChunk.text)
            .join(MemoryItem, MemoryChunk.memory_item_id == MemoryItem.id)
            .where(MemoryItem.project_id == pid)
        )
    ).scalars().all()

    haystacks = list(rows) + list(chunk_rows)
    leaks: list[str] = []

    # Exact secret membership check (catches anything redaction missed).
    for sec in secrets:
        for hay in haystacks:
            if sec in hay:
                leaks.append(sec)
                break

    # Pattern check (catches partial leaks of new secret-shaped strings).
    pattern_leaks: list[str] = []
    for pat in SECRET_PATTERNS:
        for hay in haystacks:
            m = pat.search(hay)
            if m:
                pattern_leaks.append(m.group(0))

    assert not leaks, f"plaintext secrets leaked: {leaks[:5]} (total {len(leaks)})"
    assert not pattern_leaks, (
        f"secret-shaped patterns survived redaction: {pattern_leaks[:5]} "
        f"(total {len(pattern_leaks)})"
    )
