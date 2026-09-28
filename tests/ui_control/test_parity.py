"""Parity test: `agentos ui approve` via --via-ui and --via-api emit identical
backend audit event sequences for the same logical approval action.

Skips automatically if backend (127.0.0.1:8765) or frontend (5173) aren't
serving, so the test is safe for CI environments without the live stack.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest

API = os.environ.get("AGENTOS_TEST_API", "http://127.0.0.1:8765")
FRONTEND = os.environ.get("AGENTOS_TEST_FRONTEND", "http://localhost:5173")
AGENTOS = os.environ.get(
    "AGENTOS_BIN",
    str(
        # Project root inferred from this file
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / ".venv"
        / "bin"
        / "agentos"
    ),
)


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2.0) as r:
            return r.status < 500
    except (urllib.error.URLError, OSError):
        return False


@pytest.fixture(scope="module")
def stack_up():
    if not _port_open("127.0.0.1", 8765):
        pytest.skip("backend not running on 127.0.0.1:8765")
    if not _port_open("127.0.0.1", 5173):
        pytest.skip("frontend not running on 127.0.0.1:5173")
    if not _http_ok(f"{API}/projects"):
        pytest.skip("backend /projects not reachable")
    if not shutil.which(AGENTOS) and not os.path.exists(AGENTOS):
        pytest.skip(f"agentos binary not found at {AGENTOS}")


def _create_approval(project_slug: str = "demo", tag: str = "parity") -> int:
    body = json.dumps(
        {
            "project_slug": project_slug,
            "tool": "shell",
            "action": "echo",
            "raw_input": {"cmd": f"parity-{tag}-{time.time()}"},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/approvals",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5.0) as r:
        return int(json.loads(r.read())["id"])


def _audit_events_for(approval_id: int, limit: int = 200) -> list[str]:
    """Return event_type sequence (chronological) for the given approval."""
    with urllib.request.urlopen(f"{API}/audit?limit={limit}", timeout=5.0) as r:
        items = json.loads(r.read()).get("items", [])
    matched = [
        e
        for e in items
        if (e.get("payload") or {}).get("approval_id") == approval_id
    ]
    # /audit returns newest-first; reverse for chronological.
    matched.sort(key=lambda e: e.get("id", 0))
    return [e["event_type"] for e in matched]


def _ensure_session_started():
    subprocess.run(
        [AGENTOS, "ui", "start", "--json"], check=False, capture_output=True, timeout=30
    )


def _run_approve(approval_id: int, via: str) -> dict:
    flag = "--via-api" if via == "api" else "--via-ui"
    res = subprocess.run(
        [AGENTOS, "ui", "approve", str(approval_id), flag, "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0, (
        f"agentos ui approve {flag} exit={res.returncode}\n"
        f"stdout={res.stdout!r}\nstderr={res.stderr!r}"
    )
    return json.loads(res.stdout)


def test_approve_parity_audit_sequence(stack_up):
    """--via-ui and --via-api produce byte-equal event_type sequences."""
    _ensure_session_started()

    api_id = _create_approval(tag="api")
    api_out = _run_approve(api_id, via="api")
    assert api_out["ok"], api_out

    ui_id = _create_approval(tag="ui")
    ui_out = _run_approve(ui_id, via="ui")
    assert ui_out["ok"], ui_out

    # Allow a brief moment for any trailing audit events.
    time.sleep(0.5)

    api_events = _audit_events_for(api_id)
    ui_events = _audit_events_for(ui_id)

    # Both must contain the canonical request -> decide chain.
    assert "approval.requested" in api_events
    assert "approval.decided" in api_events
    assert "approval.requested" in ui_events
    assert "approval.decided" in ui_events

    # The CORE parity claim: identical event_type sequences.
    assert api_events == ui_events, (
        f"audit event sequences differ:\n  api: {api_events}\n  ui:  {ui_events}"
    )


def test_approve_via_api_emits_decided(stack_up):
    """Sanity smoke: --via-api alone always emits approval.decided."""
    aid = _create_approval(tag="api-only")
    out = _run_approve(aid, via="api")
    assert out["ok"]
    events = _audit_events_for(aid)
    assert "approval.decided" in events


def _run_deny(approval_id: int, via: str) -> dict:
    flag = "--via-api" if via == "api" else "--via-ui"
    res = subprocess.run(
        [
            AGENTOS,
            "ui",
            "deny",
            str(approval_id),
            flag,
            "--reason",
            "parity-test",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0, (
        f"agentos ui deny {flag} exit={res.returncode}\n"
        f"stdout={res.stdout!r}\nstderr={res.stderr!r}"
    )
    return json.loads(res.stdout)


def test_deny_parity_audit_sequence(stack_up):
    """--via-ui and --via-api `deny` produce byte-equal event_type sequences."""
    _ensure_session_started()

    api_id = _create_approval(tag="deny-api")
    api_out = _run_deny(api_id, via="api")
    assert api_out["ok"], api_out

    ui_id = _create_approval(tag="deny-ui")
    ui_out = _run_deny(ui_id, via="ui")
    assert ui_out["ok"], ui_out

    time.sleep(0.5)

    api_events = _audit_events_for(api_id)
    ui_events = _audit_events_for(ui_id)

    assert "approval.requested" in api_events
    assert "approval.decided" in api_events
    assert "approval.requested" in ui_events
    assert "approval.decided" in ui_events

    assert api_events == ui_events, (
        f"audit event sequences differ:\n  api: {api_events}\n  ui:  {ui_events}"
    )


def _audit_max_id(limit: int = 200) -> int:
    """Return the largest audit event id currently visible (0 if none)."""
    with urllib.request.urlopen(f"{API}/audit?limit={limit}", timeout=5.0) as r:
        items = json.loads(r.read()).get("items", [])
    if not items:
        return 0
    return max(int(e.get("id", 0)) for e in items)


def _audit_events_since(pre_max_id: int, prefix: str, limit: int = 200) -> list[str]:
    """event_types of audit rows whose id > pre_max_id and whose event_type
    starts with `prefix`, in chronological order."""
    with urllib.request.urlopen(f"{API}/audit?limit={limit}", timeout=5.0) as r:
        items = json.loads(r.read()).get("items", [])
    matched = [
        e
        for e in items
        if int(e.get("id", 0)) > pre_max_id
        and str(e.get("event_type", "")).startswith(prefix)
    ]
    matched.sort(key=lambda e: e.get("id", 0))
    return [e["event_type"] for e in matched]


def _run_compile_adapters(via: str, project: str = "demo") -> dict:
    flag = "--via-api" if via == "api" else "--via-ui"
    res = subprocess.run(
        [
            AGENTOS,
            "ui",
            "compile-adapters",
            flag,
            "--project",
            project,
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert res.returncode == 0, (
        f"agentos ui compile-adapters {flag} exit={res.returncode}\n"
        f"stdout={res.stdout!r}\nstderr={res.stderr!r}"
    )
    return json.loads(res.stdout)


def test_compile_adapters_parity_audit_sequence(stack_up):
    """--via-ui and --via-api `compile-adapters` produce byte-equal
    `adapters.*` event_type sequences."""
    _ensure_session_started()

    api_pre = _audit_max_id()
    api_out = _run_compile_adapters(via="api")
    assert api_out.get("ok", True), api_out
    time.sleep(0.5)
    api_events = _audit_events_since(api_pre, prefix="adapters.")

    ui_pre = _audit_max_id()
    ui_out = _run_compile_adapters(via="ui")
    assert ui_out.get("ok", True), ui_out
    time.sleep(0.5)
    ui_events = _audit_events_since(ui_pre, prefix="adapters.")

    assert api_events, f"no adapters.* events emitted via api: {api_out}"
    assert ui_events, f"no adapters.* events emitted via ui: {ui_out}"

    assert api_events == ui_events, (
        f"audit event sequences differ:\n  api: {api_events}\n  ui:  {ui_events}"
    )
