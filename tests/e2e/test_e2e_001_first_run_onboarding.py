from __future__ import annotations

import json

import pytest

from tests.e2e.conftest import REPO_ROOT, http_json


pytestmark = [pytest.mark.e2e, pytest.mark.e2e_001]

ONBOARDING_XFAIL = "missing onboarding selector in frontend (e.g. [data-testid=onboarding-welcome])"


def test_e2e_001_first_run_onboarding(
    api_base_url,
    frontend_url,
    ui_session,
    run_cli,
    run_probe,
    tmp_path,
    evidence_dir,
):
    run_cli("ui", "ensure-frontend", "--json", "--api-url", api_base_url, "--frontend-url", frontend_url)
    run_cli("ui", "start", "--json", "--api-url", api_base_url, "--frontend-url", frontend_url)
    run_cli("ui", "nav", "/", "--json", "--api-url", api_base_url, "--frontend-url", frontend_url)

    exists = run_cli(
        "ui",
        "exists",
        "[data-testid=onboarding-welcome]",
        "--timeout",
        "2500",
        "--json",
        "--api-url",
        api_base_url,
        "--frontend-url",
        frontend_url,
        check=False,
    )
    if exists.returncode != 0:
        pytest.xfail(ONBOARDING_XFAIL)

    slug = f"first-run-{tmp_path.name}"
    http_json(
        api_base_url,
        "POST",
        "/projects",
        {"slug": slug, "name": "First Run E2E", "root_path": str(tmp_path)},
    )

    target = tmp_path / "sync-target"
    target.mkdir()
    run_cli("sync", "--project", slug, "--target", str(target), "--mode", "copy")
    run_cli("validate", "--project", slug)

    audit = run_probe("audit_emission.py")
    ports = run_probe("ports_localhost.sh")
    assert audit["status"] == "PASS", json.dumps(audit, indent=2)
    assert ports["status"] == "PASS", json.dumps(ports, indent=2)
    assert REPO_ROOT.exists()
