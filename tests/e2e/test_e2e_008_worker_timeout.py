from __future__ import annotations

import time

import pytest

from tests.e2e.conftest import REPO_ROOT, audit_events, http_json


WORKER_SLEEP_XFAIL = (
    "missing worker test-kind 'sleep' for timeout simulation; need to add to app/worker.py dispatch"
)


def _worker_has_sleep_kind() -> bool:
    src = (REPO_ROOT / "backend/app/worker.py").read_text(encoding="utf-8")
    return '"sleep"' in src or "'sleep'" in src


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.e2e_008,
    pytest.mark.xfail(not _worker_has_sleep_kind(), reason=WORKER_SLEEP_XFAIL, strict=False),
]


def test_e2e_008_worker_timeout(api_base_url, tmp_project, evidence_dir):
    if not _worker_has_sleep_kind():
        pytest.xfail(WORKER_SLEEP_XFAIL)

    task = http_json(
        api_base_url,
        "POST",
        "/worker/tasks",
        {
            "project_id": tmp_project["id"],
            "kind": "sleep",
            "payload": {"seconds": 10},
            "timeout_seconds": 2,
            "max_attempts": 1,
        },
    )

    deadline = time.monotonic() + 20.0
    latest = task
    while time.monotonic() < deadline:
        rows = http_json(api_base_url, "GET", "/worker/tasks?limit=100")
        latest = next(r for r in rows if int(r["id"]) == int(task["id"]))
        if latest["status"] == "timed_out":
            break
        time.sleep(1.0)

    assert latest["status"] == "timed_out", latest
    events = audit_events(api_base_url, tmp_project["slug"])
    assert any(
        e["event_type"] == "task.timed_out" and e["payload"].get("task_id") == task["id"]
        for e in events
    )
