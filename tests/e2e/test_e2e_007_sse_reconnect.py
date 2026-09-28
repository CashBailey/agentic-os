from __future__ import annotations

import json
import os
import subprocess
import threading
import time

import pytest

from tests.e2e.conftest import http_json


BACKEND_KILL_XFAIL = (
    "set AGENTOS_ALLOW_BACKEND_KILL=1 to allow this test; otherwise unsafe to kill uvicorn in shared env"
)
SSE_CLIENT_XFAIL = "missing sseclient-py; install or use httpx stream"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.e2e_007,
    pytest.mark.xfail(
        os.environ.get("AGENTOS_ALLOW_BACKEND_KILL") != "1",
        reason=BACKEND_KILL_XFAIL,
        strict=False,
    ),
]


def _wait_health(api_base_url: str, timeout_s: float = 45.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            http_json(api_base_url, "GET", "/healthz", timeout=2.0)
            return
        except Exception:
            time.sleep(1.0)
    raise AssertionError("backend did not return /healthz after restart")


def test_e2e_007_sse_reconnect(api_base_url, tmp_project, evidence_dir):
    if os.environ.get("AGENTOS_ALLOW_BACKEND_KILL") != "1":
        pytest.xfail(BACKEND_KILL_XFAIL)
    try:
        import httpx
    except ImportError:
        pytest.xfail(SSE_CLIENT_XFAIL)

    seen: list[dict] = []
    stop = threading.Event()

    def reader() -> None:
        last_id = 0
        while not stop.is_set():
            try:
                with httpx.stream("GET", f"{api_base_url}/events?since={last_id}", timeout=10.0) as r:
                    for line in r.iter_lines():
                        if stop.is_set():
                            return
                        if not line.startswith("data: "):
                            continue
                        data = json.loads(line.removeprefix("data: "))
                        if "id" in data:
                            last_id = max(last_id, int(data["id"]))
                        seen.append(data)
            except Exception:
                time.sleep(0.5)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    http_json(api_base_url, "POST", "/projects", {"slug": f"{tmp_project['slug']}-a", "name": "SSE A", "root_path": "/tmp/a"})
    time.sleep(2.0)

    subprocess.run(["pkill", "-f", "uvicorn.*app.main"], check=False)
    _wait_health(api_base_url)
    http_json(api_base_url, "POST", "/projects", {"slug": f"{tmp_project['slug']}-b", "name": "SSE B", "root_path": "/tmp/b"})
    time.sleep(3.0)
    stop.set()
    t.join(timeout=2.0)

    assert any(e.get("event_type") == "project.created" and e.get("payload", {}).get("slug", "").endswith("-b") for e in seen)
