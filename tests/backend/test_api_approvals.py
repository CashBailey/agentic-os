import uuid

import pytest


@pytest.mark.db
@pytest.mark.asyncio
async def test_approval_flow(client):
    slug = f"app-{uuid.uuid4().hex[:8]}"
    pr = await client.post("/projects", json={"slug": slug, "name": "A", "root_path": "/tmp"})
    pid = pr.json()["id"]

    r = await client.post(
        "/approvals",
        json={
            "project_id": pid,
            "tool": "bash",
            "action": "shell",
            "raw_input": {"args": ["git", "push"]},
            "risk": "medium",
        },
    )
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert r.json()["status"] == "pending"

    r = await client.post(f"/approvals/{aid}/decide", json={"decision": "approved", "reason": "ok"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    r = await client.post(f"/approvals/{aid}/release")
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "released"
    assert "release_token" in out
