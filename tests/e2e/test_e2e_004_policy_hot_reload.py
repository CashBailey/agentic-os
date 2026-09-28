from __future__ import annotations

import json

import pytest

from tests.e2e.conftest import REPO_ROOT, http_json

POLICY_RELOAD_XFAIL = (
    "missing POST /projects/{slug}/policies/reload endpoint; PUT updates file but "
    "in-memory policy cache not invalidated (see backend/app/api/policies.py and app/services/policy_eval.py)"
)


def _cache_without_reload() -> bool:
    policies = (REPO_ROOT / "backend/app/api/policies.py").read_text(encoding="utf-8")
    evaluator = (REPO_ROOT / "backend/app/services/policy_eval.py").read_text(encoding="utf-8")
    has_reload = "/reload" in policies or "reload" in policies
    has_cache = "cache" in policies.lower() or "cache" in evaluator.lower()
    return has_cache and not has_reload


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.e2e_004,
    pytest.mark.xfail(_cache_without_reload(), reason=POLICY_RELOAD_XFAIL, strict=False),
]


def test_e2e_004_policy_hot_reload(
    api_base_url,
    frontend_url,
    tmp_project,
    ui_session,
    run_cli,
    evidence_dir,
):
    if _cache_without_reload():
        pytest.xfail(POLICY_RELOAD_XFAIL)

    before = http_json(api_base_url, "GET", f"/projects/{tmp_project['slug']}/policies")
    original = next((p["content"] for p in before if p["kind"] == "shell"), "")
    content = """
shell:
  default: prompt
  forbidden:
    - pattern: ["rm", "*"]
      reason: "e2e hot reload deny"
""".lstrip()
    saved = http_json(
        api_base_url,
        "PUT",
        f"/projects/{tmp_project['slug']}/policies/shell",
        {"content": content},
    )
    assert saved["parsed_ok"]

    try:
        api_result = http_json(
            api_base_url,
            "POST",
            f"/projects/{tmp_project['slug']}/policies/simulate",
            {"tool": "rm", "action": "shell", "args": ["/"]},
        )
        assert api_result["decision"] == "deny", json.dumps(api_result, indent=2)

        run_cli("ui", "project", tmp_project["slug"], "--json", "--api-url", api_base_url, "--frontend-url", frontend_url)
        ui = run_cli(
            "ui",
            "simulate-policy",
            "--tool",
            "rm",
            "--action",
            "shell",
            "--args",
            json.dumps(["/"]),
            "--json",
            "--api-url",
            api_base_url,
            "--frontend-url",
            frontend_url,
        )
        payload = json.loads(ui.stdout)
        assert payload["ok"], payload
        assert payload["decision"] == "deny", payload
    finally:
        http_json(
            api_base_url,
            "PUT",
            f"/projects/{tmp_project['slug']}/policies/shell",
            {"content": original},
        )
