import uuid

import pytest


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_memory_redacts(client):
    slug = f"mem-{uuid.uuid4().hex[:8]}"
    await client.post("/projects", json={"slug": slug, "name": "M", "root_path": "/tmp"})
    secret_body = "deploy with password=hunter2 and AKIAABCDEFGHIJKLMNOP"
    r = await client.post(
        f"/projects/{slug}/memory",
        json={"kind": "note", "title": "t", "body": secret_body, "tags": ["x"]},
    )
    assert r.status_code == 201, r.text
    body = r.json()["body"]
    assert "hunter2" not in body
    assert "AKIAABCDEFGHIJKLMNOP" not in body
    assert "[REDACTED]" in body

    r = await client.get(f"/projects/{slug}/memory")
    assert r.status_code == 200
    assert len(r.json()) >= 1
