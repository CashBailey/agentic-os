"""Contract tests: hit every FastAPI endpoint via TestClient/AsyncClient with
valid/invalid/boundary payloads.

Tests that don't require the DB run unconditionally. Tests that need DB rows are
marked with @pytest.mark.db and skipped when SKIP_DB_TESTS or DB unreachable.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


# =========================================================================
# Health / status
# =========================================================================

async def test_healthz_ok(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_healthz_method_not_allowed(client):
    r = await client.post("/healthz")
    assert r.status_code in (405, 404)


async def test_auth_status(client):
    r = await client.get("/auth-status")
    assert r.status_code == 200


async def test_skills(client):
    r = await client.get("/skills")
    assert r.status_code == 200


async def test_workflows(client):
    r = await client.get("/workflows")
    assert r.status_code == 200


async def test_events_endpoint_registered(app):
    # /events is an SSE stream that would hang a normal client.get(). Verify
    # it's routed by inspecting the FastAPI route table instead.
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/events" in paths


# =========================================================================
# Projects — validation
# =========================================================================

@pytest.mark.db
async def test_create_project_valid(client):
    slug = f"contract-{uuid.uuid4().hex[:8]}"
    r = await client.post(
        "/projects", json={"slug": slug, "name": "C", "root_path": "/tmp"}
    )
    assert r.status_code == 201
    assert r.json()["slug"] == slug


async def test_create_project_missing_slug(client):
    r = await client.post("/projects", json={"name": "x", "root_path": "/tmp"})
    assert r.status_code == 422


async def test_create_project_empty_body(client):
    r = await client.post("/projects", json={})
    assert r.status_code == 422


async def test_create_project_wrong_types(client):
    r = await client.post(
        "/projects", json={"slug": 123, "name": "x", "root_path": "/tmp"}
    )
    assert r.status_code == 422


@pytest.mark.db
async def test_get_unknown_project_404(client):
    r = await client.get(f"/projects/does-not-exist-{uuid.uuid4().hex[:6]}")
    assert r.status_code == 404


@pytest.mark.db
async def test_list_projects(client):
    r = await client.get("/projects")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.db
async def test_create_project_duplicate_slug(client):
    slug = f"dup-{uuid.uuid4().hex[:8]}"
    payload = {"slug": slug, "name": "n", "root_path": "/tmp"}
    r1 = await client.post("/projects", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/projects", json=payload)
    assert r2.status_code == 409


# =========================================================================
# Memory
# =========================================================================

@pytest.mark.db
async def test_memory_list_for_unknown_project_404(client):
    r = await client.get(f"/projects/no-such-{uuid.uuid4().hex[:6]}/memory")
    assert r.status_code == 404


async def test_memory_create_missing_body(client):
    r = await client.post("/projects/any/memory", json={"kind": "note"})
    # 404 (project missing) or 422 (body missing) both acceptable; never 500.
    assert r.status_code in (404, 422)


async def test_memory_create_wrong_kind_type(client):
    r = await client.post(
        "/projects/any/memory", json={"kind": 1, "body": "x"}
    )
    assert r.status_code in (404, 422)


async def test_memory_semantic_invalid_top_k(client):
    # top_k expected int; passing string forces 422 before DB lookup
    r = await client.post(
        "/projects/any/memory/search/semantic",
        json={"query": "hi", "top_k": "not-an-int"},
    )
    assert r.status_code in (404, 422)


# =========================================================================
# Approvals
# =========================================================================

async def test_approvals_create_validation_missing_fields(client):
    r = await client.post("/approvals", json={})
    assert r.status_code == 422


async def test_approvals_create_missing_tool(client):
    r = await client.post(
        "/approvals",
        json={"project_slug": "x", "action": "run", "raw_input": {}},
    )
    assert r.status_code in (404, 422)


async def test_approvals_decide_invalid_id_type(client):
    r = await client.post("/approvals/not-an-int/decide", json={"decision": "approved"})
    assert r.status_code == 422


async def test_approvals_decide_missing_body(client):
    r = await client.post("/approvals/1/decide", json={})
    assert r.status_code in (404, 422)


async def test_approvals_release_unknown(client):
    r = await client.post("/approvals/999999/release")
    assert r.status_code in (404, 422)


async def test_approvals_execute_bad_token(client):
    r = await client.post(
        "/approvals/1/execute",
        json={"release_token": "not-a-uuid", "execution_result": {}},
    )
    assert r.status_code in (404, 422)


@pytest.mark.db
async def test_approvals_list(client):
    r = await client.get("/approvals")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# =========================================================================
# Adapters
# =========================================================================

@pytest.mark.db
async def test_adapters_list_unknown_project_404(client):
    r = await client.get(f"/projects/none-{uuid.uuid4().hex[:6]}/adapters")
    assert r.status_code == 404


@pytest.mark.db
async def test_adapters_compile_unknown_project_404(client):
    r = await client.post(f"/projects/none-{uuid.uuid4().hex[:6]}/adapters/compile")
    assert r.status_code == 404


async def test_adapters_diff_bad_cli(client):
    # Unknown project → 404 regardless of cli
    r = await client.get("/projects/none/adapters/codex/diff")
    assert r.status_code in (404, 422)


# =========================================================================
# Policies
# =========================================================================

@pytest.mark.db
async def test_policies_list_unknown_project_404(client):
    r = await client.get(f"/projects/none-{uuid.uuid4().hex[:6]}/policies")
    assert r.status_code == 404


async def test_policies_update_invalid_kind(client):
    # Unknown project will return 404 first; with valid project, unknown kind
    # would 404 too. Either way: not a 500.
    r = await client.put(
        "/projects/none/policies/not-a-kind",
        json={"content": "shell: {}"},
    )
    assert r.status_code in (404, 422)


async def test_policies_update_missing_body(client):
    r = await client.put("/projects/none/policies/shell", json={})
    assert r.status_code in (404, 422)


async def test_policies_simulate_missing_fields(client):
    r = await client.post("/projects/none/policies/simulate", json={})
    assert r.status_code in (404, 422)


# =========================================================================
# Worker / tasks
# =========================================================================

@pytest.mark.db
async def test_worker_list(client):
    r = await client.get("/worker/tasks")
    assert r.status_code in (200, 404)


async def test_worker_create_missing_kind(client):
    r = await client.post("/worker/tasks", json={"payload": {}})
    assert r.status_code in (404, 422)


async def test_worker_create_negative_max_attempts(client):
    # Boundary: max_attempts is int but no explicit constraint; accept 200/201/404/422
    r = await client.post(
        "/worker/tasks",
        json={"kind": "noop", "max_attempts": -1, "timeout_seconds": 1},
    )
    assert r.status_code in (200, 201, 404, 422)


async def test_worker_cancel_bad_id(client):
    r = await client.post("/worker/tasks/not-an-int/cancel")
    assert r.status_code == 422


# =========================================================================
# Decisions
# =========================================================================

@pytest.mark.db
async def test_decisions_list_unknown_project_404(client):
    r = await client.get(f"/projects/none-{uuid.uuid4().hex[:6]}/decisions")
    assert r.status_code == 404


async def test_decisions_create_validation(client):
    r = await client.post("/projects/none/decisions", json={})
    assert r.status_code in (404, 422)


# =========================================================================
# Sessions
# =========================================================================

@pytest.mark.db
async def test_sessions_list_unknown_project_404(client):
    r = await client.get(f"/projects/none-{uuid.uuid4().hex[:6]}/sessions")
    assert r.status_code == 404


async def test_sessions_end_validation(client):
    r = await client.post("/projects/none/sessions/end", json={})
    assert r.status_code in (404, 422)


# =========================================================================
# Context
# =========================================================================

@pytest.mark.db
async def test_context_list_unknown_project_404(client):
    r = await client.get(f"/projects/none-{uuid.uuid4().hex[:6]}/context")
    assert r.status_code == 404


async def test_context_update_bad_id(client):
    r = await client.put(
        "/projects/none/context/not-an-int", json={"content": "x"}
    )
    assert r.status_code == 422


# =========================================================================
# Audit
# =========================================================================

@pytest.mark.db
async def test_audit_list(client):
    r = await client.get("/audit")
    # Either an AuditPage object or list; just no 500.
    assert r.status_code in (200, 404, 422)


async def test_audit_invalid_query_types(client):
    r = await client.get("/audit?limit=not-an-int")
    assert r.status_code in (200, 404, 422)


# =========================================================================
# Export / Import
# =========================================================================

@pytest.mark.db
async def test_export_markdown(client):
    r = await client.get("/export/markdown")
    assert r.status_code in (200, 404)


async def test_import_markdown_empty_body(client):
    r = await client.post("/import/markdown", json={})
    assert r.status_code in (200, 400, 404, 422)


# =========================================================================
# 404 for unknown routes
# =========================================================================

async def test_unknown_route_404(client):
    r = await client.get("/this-does-not-exist-xyz")
    assert r.status_code == 404
