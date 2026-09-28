from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.e2e.conftest import REPO_ROOT, audit_events, http_json


def _missing_adapter() -> str | None:
    for name in ("claude", "codex", "gemini"):
        if not (REPO_ROOT / "agent-os" / "adapters" / f"{name}.yaml").exists():
            return name
    return None


_MISSING = _missing_adapter()
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.e2e_005,
    pytest.mark.xfail(
        _MISSING is not None,
        reason=f"missing adapter subtree: agent-os/adapters/{_MISSING}",
        strict=False,
    ),
]


def test_e2e_005_multi_cli_coexistence(
    api_base_url,
    tmp_path,
    run_probe,
    evidence_dir,
):
    if _MISSING:
        pytest.xfail(f"missing adapter subtree: agent-os/adapters/{_MISSING}")

    probe = run_probe("install_adapter_subtree.sh")
    assert probe["status"] == "PASS", probe

    projects = [
        http_json(
            api_base_url,
            "POST",
            "/projects",
            {
                "slug": f"multi-cli-{name}-{tmp_path.name}",
                "name": f"Multi CLI {name}",
                "root_path": str(tmp_path / name),
            },
        )
        for name in ("claude", "codex", "gemini")
    ]

    def compile_one(project: dict) -> dict:
        return http_json(api_base_url, "POST", f"/projects/{project['slug']}/adapters/compile")

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(compile_one, projects))

    assert all(r["status"] == "queued" and r["task_id"] for r in results)
    for project, result in zip(projects, results):
        events = audit_events(api_base_url, project["slug"])
        queued = [
            e
            for e in events
            if e["event_type"] == "adapter.compile.queued"
            and e["payload"].get("task_id") == result["task_id"]
        ]
        assert queued, f"missing compile audit for {project['slug']}"
        assert all(e["project_id"] == project["id"] for e in events)
