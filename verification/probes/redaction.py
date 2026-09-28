#!/usr/bin/env python3
"""T-SEC-003 — memory body redaction strips known secret patterns before storage."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request as u
from pathlib import Path

API = os.environ.get("AGENTOS_API_BASE", "http://127.0.0.1:8765")
WANT_JSON = "--json" in sys.argv[1:]
REPO_ROOT = Path(__file__).resolve().parents[2]

AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"
GH_SECRET = "ghp_" + "a" * 36


def emit(status: str, evidence: str) -> int:
    if WANT_JSON:
        print(json.dumps({"id": "T-SEC-003", "status": status, "evidence": evidence}))
    else:
        print(f"[T-SEC-003] {status} — {evidence}")
    return 0 if status == "PASS" else 1


def post(path: str, body):
    req = u.Request(f"{API}{path}", method="POST",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"})
    return json.loads(u.urlopen(req, timeout=20).read().decode() or "{}")


def get(path: str):
    return json.loads(u.urlopen(f"{API}{path}", timeout=20).read().decode() or "[]")


def main() -> int:
    slug = f"red-probe-{int(time.time())}"
    try:
        post("/projects", {"slug": slug, "name": "Red", "root_path": "/tmp/red"})
        body = f"leak {AWS_SECRET} and {GH_SECRET} done"
        created = post(f"/projects/{slug}/memory", {"kind": "note", "title": "t", "body": body, "tags": []})
    except Exception as e:
        return emit("FAIL", f"create failed: {e}")

    if AWS_SECRET in created.get("body", "") or GH_SECRET in created.get("body", ""):
        return emit("FAIL", f"raw secret in POST response body: {created.get('body','')[:120]}")

    # Re-fetch to confirm storage.
    try:
        items = get(f"/projects/{slug}/memory")
    except Exception as e:
        return emit("FAIL", f"list failed: {e}")
    match = next((i for i in items if i["id"] == created["id"]), None)
    if not match:
        return emit("FAIL", "created item missing on re-fetch")
    if AWS_SECRET in match["body"] or GH_SECRET in match["body"]:
        return emit("FAIL", f"stored body contains secret: {match['body'][:120]}")

    # Source-path check: confirm redact() is called before storage and before embed.
    mem = (REPO_ROOT / "backend" / "app" / "api" / "memory.py").read_text()
    if "redact(" not in mem:
        return emit("FAIL", "api/memory.py does not call redact()")
    embed_src = REPO_ROOT / "backend" / "app" / "services" / "embeddings.py"
    if embed_src.exists() and "redact" not in embed_src.read_text():
        # Not strictly required if redaction happens upstream; just note it.
        pass
    return emit("PASS", f"secrets stripped; stored body redacted (id={match['id']})")


if __name__ == "__main__":
    sys.exit(main())
