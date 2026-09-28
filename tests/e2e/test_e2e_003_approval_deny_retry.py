from __future__ import annotations

import json
import subprocess

import pytest

from tests.e2e.conftest import create_approval, release_and_execute


pytestmark = [pytest.mark.e2e, pytest.mark.e2e_003]


def _psql(sql: str) -> str:
    proc = subprocess.run(
        [
            "docker",
            "exec",
            "agentos-db",
            "psql",
            "-U",
            "agentos",
            "-d",
            "agentos",
            "-t",
            "-A",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_e2e_003_approval_deny_retry(
    api_base_url,
    frontend_url,
    tmp_project,
    ui_session,
    run_cli,
    evidence_dir,
):
    denied = create_approval(api_base_url, tmp_project["slug"], "deny-retry-deny")
    approved = create_approval(api_base_url, tmp_project["slug"], "deny-retry-approve")

    run_cli(
        "ui",
        "deny",
        str(denied["id"]),
        "--reason",
        "test",
        "--json",
        "--api-url",
        api_base_url,
        "--frontend-url",
        frontend_url,
    )
    run_cli(
        "ui",
        "approve",
        str(approved["id"]),
        "--via-api",
        "--json",
        "--api-url",
        api_base_url,
        "--frontend-url",
        frontend_url,
    )
    release_and_execute(api_base_url, approved["id"])

    rows = _psql(
        "SELECT payload->>'decision' FROM audit_events "
        f"WHERE event_type='approval.decided' AND payload->>'approval_id' IN ('{denied['id']}','{approved['id']}') "
        "ORDER BY id ASC;"
    ).splitlines()
    assert rows == ["denied", "approved"], json.dumps(rows)
