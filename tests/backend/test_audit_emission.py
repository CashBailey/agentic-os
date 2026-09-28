import uuid

import pytest


@pytest.mark.db
@pytest.mark.asyncio
async def test_audit_events_emitted_for_full_flow(client):
    slug = f"audit-{uuid.uuid4().hex[:8]}"
    # 1. project.created
    pr = await client.post(
        "/projects", json={"slug": slug, "name": "A", "root_path": "/tmp"}
    )
    assert pr.status_code == 201, pr.text

    # 2. approval.requested (with project_slug)
    r = await client.post(
        "/approvals",
        json={
            "project_slug": slug,
            "tool": "bash",
            "action": "shell",
            "raw_input": {"args": ["echo", "hi"]},
            "risk": "low",
        },
    )
    assert r.status_code == 201, r.text
    aid = r.json()["id"]

    # 3. approval.decided
    r = await client.post(
        f"/approvals/{aid}/decide",
        json={"decision": "approved", "reason": "ok"},
    )
    assert r.status_code == 200

    # 4. approval.released
    r = await client.post(f"/approvals/{aid}/release")
    assert r.status_code == 200
    token = r.json()["release_token"]

    # 5. approval.executed
    r = await client.post(
        f"/approvals/{aid}/execute",
        json={"release_token": token, "execution_result": {"ok": True}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "executed"

    # Now query /audit?project=slug and assert ≥ 5 events with the expected types.
    page = await client.get(f"/audit?project={slug}&limit=200")
    assert page.status_code == 200
    items = page.json()["items"]
    assert len(items) >= 5, items
    types = {ev["event_type"] for ev in items}
    expected = {
        "project.created",
        "approval.requested",
        "approval.decided",
        "approval.released",
        "approval.executed",
    }
    missing = expected - types
    assert not missing, f"missing audit events: {missing}; got: {types}"
