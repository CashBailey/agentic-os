import uuid

import pytest


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_with_valid_slug_resolves_project_id(client):
    slug = f"res-{uuid.uuid4().hex[:8]}"
    pr = await client.post(
        "/projects", json={"slug": slug, "name": "R", "root_path": "/tmp"}
    )
    pid = pr.json()["id"]
    r = await client.post(
        "/approvals",
        json={
            "project_slug": slug,
            "tool": "bash",
            "action": "shell",
            "raw_input": {"args": ["x"]},
            "risk": "low",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["project_id"] == pid


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_with_unknown_slug_returns_404(client):
    r = await client.post(
        "/approvals",
        json={
            "project_slug": f"missing-{uuid.uuid4().hex}",
            "tool": "bash",
            "action": "shell",
            "raw_input": {},
            "risk": "low",
        },
    )
    assert r.status_code == 404, r.text


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_without_project_identifier_returns_422(client):
    r = await client.post(
        "/approvals",
        json={
            "tool": "bash",
            "action": "shell",
            "raw_input": {},
            "risk": "low",
        },
    )
    assert r.status_code == 422, r.text
