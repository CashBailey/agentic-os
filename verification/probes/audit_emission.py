#!/usr/bin/env python3
"""T-AUD-PROBE-001 — full approval lifecycle emits the expected audit chain.

Expected event_types, in order:
  project.created, approval.requested, approval.decided, approval.released, approval.executed
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError

API = os.environ.get("AGENTOS_API_BASE", "http://127.0.0.1:8765")
WANT_JSON = "--json" in sys.argv[1:]
EXPECTED = [
    "project.created",
    "approval.requested",
    "approval.decided",
    "approval.released",
    "approval.executed",
]


def emit(status: str, evidence: str) -> int:
    if WANT_JSON:
        print(json.dumps({"id": "T-AUD-PROBE-001", "status": status, "evidence": evidence}))
    else:
        print(f"[T-AUD-PROBE-001] {status} — {evidence}")
    return 0 if status == "PASS" else 1


def http(method: str, path: str, body=None):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API}{path}", method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode() or "{}")


def psql(sql: str) -> str:
    proc = subprocess.run(
        ["docker", "exec", "agentos-db", "psql", "-U", "agentos", "-d", "agentos",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"psql failed: {proc.stderr}")
    return proc.stdout.strip()


def main() -> int:
    slug = f"audit-probe-{int(time.time())}"
    try:
        proj = http("POST", "/projects", {"slug": slug, "name": "AuditProbe", "root_path": "/tmp/audit-probe"})
        pid = proj["id"]
        appr = http("POST", "/approvals", {
            "project_slug": slug, "tool": "shell", "action": "echo hi",
            "raw_input": {"cmd": "echo hi"}, "normalized": {"cmd": "echo hi"}, "risk": "low",
            "agent_reason": "probe", "policy_reason": "probe", "ttl_seconds": 600,
        })
        aid = appr["id"]
        http("POST", f"/approvals/{aid}/decide", {"decision": "approved", "reason": "probe"})
        rel = http("POST", f"/approvals/{aid}/release", None)
        token = rel["release_token"]
        http("POST", f"/approvals/{aid}/execute", {"release_token": token, "execution_result": {"ok": True}})
    except (HTTPError, URLError, RuntimeError, KeyError) as e:
        return emit("FAIL", f"lifecycle setup failed: {e}")

    try:
        rows = psql(
            f"SELECT event_type FROM audit_events WHERE project_id = {pid} ORDER BY id ASC;"
        )
    except RuntimeError as e:
        return emit("FAIL", str(e))

    got = [r for r in rows.splitlines() if r]
    if got != EXPECTED:
        return emit("FAIL", f"event chain mismatch: got={got} expected={EXPECTED}")
    return emit("PASS", f"emitted in order: {','.join(got)}")


if __name__ == "__main__":
    sys.exit(main())
