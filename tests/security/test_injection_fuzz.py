"""T-SEC-INJECT — fuzz slug/memory_id with SQLi + path traversal payloads.

Asserts: no 500s, no raw SQL errors/tracebacks in response bodies, and
the projects table still exists after the run.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.security, pytest.mark.asyncio]

PAYLOADS = [
    "'; DROP TABLE projects;--",
    "' OR '1'='1",
    "../../etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",
    "%00",
    "<script>alert(1)</script>",
    "%27%20OR%201=1--",
    "admin'--",
]

LEAK_MARKERS = [
    "Traceback",
    "psycopg",
    "sqlalchemy.exc",
    "InvalidTextRepresentation",
    "syntax error at or near",
    "ProgrammingError",
    "OperationalError",
    "DataError",
]


async def test_injection_fuzz(db_reachable, async_client, db_session):
    if not db_reachable:
        pytest.skip("Postgres backend not reachable")

    from sqlalchemy import text

    for payload in PAYLOADS:
        # GET project
        r = await async_client.get(f"/projects/{payload}")
        assert r.status_code != 500, f"500 on GET /projects/{payload!r}: {r.text[:200]}"
        for marker in LEAK_MARKERS:
            assert marker not in r.text, f"leak marker {marker!r} in body for {payload!r}"

        # GET project memory
        r = await async_client.get(f"/projects/{payload}/memory")
        assert r.status_code != 500, f"500 on GET memory {payload!r}: {r.text[:200]}"
        for marker in LEAK_MARKERS:
            assert marker not in r.text, f"leak marker {marker!r} in body for {payload!r}"

        # POST memory with the fuzzed slug
        r = await async_client.post(
            f"/projects/{payload}/memory",
            json={"kind": "note", "title": "t", "body": "x", "tags": []},
        )
        assert r.status_code != 500, f"500 on POST memory {payload!r}: {r.text[:200]}"
        for marker in LEAK_MARKERS:
            assert marker not in r.text, f"leak marker {marker!r} in body for {payload!r}"

        # Fuzz memory_id position too (numeric path param).
        r = await async_client.get(f"/projects/demo/memory/{payload}")
        # 404/422 are fine; just no 500 / leaks.
        assert r.status_code != 500, f"500 on memory_id fuzz {payload!r}: {r.text[:200]}"
        for marker in LEAK_MARKERS:
            assert marker not in r.text, f"leak marker {marker!r} on memory_id {payload!r}"

    # Sanity: projects table still exists.
    row = (
        await db_session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name='projects' LIMIT 1"
            )
        )
    ).first()
    assert row is not None, "projects table missing after injection fuzz (DROP succeeded!)"
