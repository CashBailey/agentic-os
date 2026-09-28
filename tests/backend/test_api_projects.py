import asyncio
import uuid

import pytest


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_and_list_project(client):
    slug = f"proj-{uuid.uuid4().hex[:8]}"
    r = await client.post("/projects", json={"slug": slug, "name": "Test", "root_path": "/tmp"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["slug"] == slug

    r = await client.get("/projects")
    assert r.status_code == 200
    assert any(p["slug"] == slug for p in r.json())

    r = await client.get(f"/projects/{slug}")
    assert r.status_code == 200
    assert r.json()["slug"] == slug


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_project_duplicate_slug_race_returns_409():
    """A TOCTOU race on slug uniqueness must surface as 409, not an unhandled 500.

    The sequential pre-check in ``create_project`` already returns 409 for an
    *already-existing* slug, but if a concurrent request inserts the same slug
    between this request's pre-check and its INSERT (possible under
    ``uvicorn --workers N`` / gunicorn), the INSERT hits the unique constraint
    and raises ``IntegrityError``. Without explicit handling that becomes a raw
    HTTP 500.

    This opens that exact race deterministically against the real unique
    constraint (no mocks): session B stages a conflicting, *uncommitted* INSERT
    (invisible to A under READ COMMITTED), so A's pre-check misses it and A
    blocks on its own INSERT; B then commits, forcing a genuine ``IntegrityError``
    inside A. The handler must translate that into ``HTTPException(409)``.
    """
    from sqlalchemy import text
    from fastapi import HTTPException

    from app.api.projects import create_project
    from app.db.session import AsyncSessionLocal
    from app.models.projects import Project
    from app.schemas.projects import ProjectCreate

    slug = f"race-{uuid.uuid4().hex[:12]}"
    body = ProjectCreate(slug=slug, name="race-a", root_path="/tmp/race-a")

    async with AsyncSessionLocal() as sess_a, AsyncSessionLocal() as sess_b:
        try:
            # B stages a conflicting INSERT but does not commit (invisible to A).
            sess_b.add(Project(slug=slug, name="race-b", root_path="/tmp/race-b"))
            await sess_b.flush()

            # A runs the endpoint logic; its pre-check misses B's uncommitted
            # row, so it proceeds to INSERT and blocks on the unique index.
            task = asyncio.create_task(create_project(body, sess_a))
            await asyncio.sleep(0.3)  # let A reach the blocking INSERT

            # B commits → A's blocked INSERT now violates the unique constraint.
            await sess_b.commit()

            with pytest.raises(HTTPException) as excinfo:
                await task
            assert excinfo.value.status_code == 409, excinfo.value
        finally:
            # Remove whichever row landed so the test leaves no residue.
            async with AsyncSessionLocal() as cleanup:
                await cleanup.execute(text("DELETE FROM projects WHERE slug = :s"), {"s": slug})
                await cleanup.commit()
