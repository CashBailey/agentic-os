import uuid

import pytest


@pytest.mark.db
@pytest.mark.asyncio
async def test_full_lifecycle_to_executed(client):
    slug = f"life-{uuid.uuid4().hex[:8]}"
    await client.post(
        "/projects", json={"slug": slug, "name": "L", "root_path": "/tmp"}
    )
    r = await client.post(
        "/approvals",
        json={
            "project_slug": slug,
            "tool": "bash",
            "action": "shell",
            "raw_input": {"args": ["ls"]},
            "risk": "low",
        },
    )
    aid = r.json()["id"]
    assert r.json()["status"] == "pending"

    r = await client.post(
        f"/approvals/{aid}/decide", json={"decision": "approved"}
    )
    assert r.json()["status"] == "approved"

    r = await client.post(f"/approvals/{aid}/release")
    assert r.json()["status"] == "released"
    token = r.json()["release_token"]

    r = await client.post(
        f"/approvals/{aid}/execute",
        json={"release_token": token, "execution_result": {"exit": 0}},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "executed"


@pytest.mark.db
@pytest.mark.asyncio
async def test_execute_rejects_wrong_token(client):
    slug = f"badtok-{uuid.uuid4().hex[:8]}"
    await client.post(
        "/projects", json={"slug": slug, "name": "T", "root_path": "/tmp"}
    )
    r = await client.post(
        "/approvals",
        json={
            "project_slug": slug,
            "tool": "bash",
            "action": "shell",
            "raw_input": {"args": ["ls"]},
            "risk": "low",
        },
    )
    aid = r.json()["id"]
    await client.post(f"/approvals/{aid}/decide", json={"decision": "approved"})
    await client.post(f"/approvals/{aid}/release")

    bogus = str(uuid.uuid4())
    r = await client.post(
        f"/approvals/{aid}/execute",
        json={"release_token": bogus, "execution_result": {}},
    )
    assert r.status_code == 400, r.text


@pytest.mark.db
@pytest.mark.asyncio
async def test_execute_requires_released_state(client):
    slug = f"notrel-{uuid.uuid4().hex[:8]}"
    await client.post(
        "/projects", json={"slug": slug, "name": "T", "root_path": "/tmp"}
    )
    r = await client.post(
        "/approvals",
        json={
            "project_slug": slug,
            "tool": "bash",
            "action": "shell",
            "raw_input": {"args": ["ls"]},
            "risk": "low",
        },
    )
    aid = r.json()["id"]
    # Attempt execute on pending approval — should 409.
    r = await client.post(
        f"/approvals/{aid}/execute",
        json={"release_token": str(uuid.uuid4()), "execution_result": {}},
    )
    assert r.status_code == 409
