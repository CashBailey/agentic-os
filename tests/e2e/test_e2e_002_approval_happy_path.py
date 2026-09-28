from __future__ import annotations

import json

import pytest

from tests.e2e.conftest import approval_by_id, create_approval, release_and_execute


pytestmark = [pytest.mark.e2e, pytest.mark.e2e_002]


def test_e2e_002_approval_happy_path(
    api_base_url,
    frontend_url,
    tmp_project,
    ui_session,
    run_cli,
    run_probe,
    evidence_dir,
):
    first = create_approval(api_base_url, tmp_project["slug"], "happy-ui")
    run_cli(
        "ui",
        "approve",
        str(first["id"]),
        "--via-ui",
        "--json",
        "--api-url",
        api_base_url,
        "--frontend-url",
        frontend_url,
    )
    assert approval_by_id(api_base_url, first["id"])["status"] == "approved"
    executed = release_and_execute(api_base_url, first["id"])
    assert executed["status"] == "executed"

    second = create_approval(api_base_url, tmp_project["slug"], "happy-api")
    run_cli(
        "ui",
        "approve",
        str(second["id"]),
        "--via-api",
        "--json",
        "--api-url",
        api_base_url,
        "--frontend-url",
        frontend_url,
    )
    assert approval_by_id(api_base_url, second["id"])["status"] == "approved"
    release_and_execute(api_base_url, second["id"])

    audit = run_probe("audit_emission.py")
    assert audit["status"] == "PASS", json.dumps(audit, indent=2)
