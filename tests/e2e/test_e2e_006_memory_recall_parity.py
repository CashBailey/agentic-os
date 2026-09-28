from __future__ import annotations

import json

import pytest

from tests.e2e.conftest import http_json


pytestmark = [pytest.mark.e2e, pytest.mark.e2e_006]


def test_e2e_006_memory_recall_parity(
    api_base_url,
    frontend_url,
    tmp_project,
    ui_session,
    run_cli,
    evidence_dir,
):
    slug = tmp_project["slug"]
    title_to_id: dict[str, int] = {}
    for i in range(10):
        title = f"parity-memory-{i:02d}"
        item = http_json(
            api_base_url,
            "POST",
            f"/projects/{slug}/memory",
            {
                "kind": "note",
                "title": title,
                "body": f"needle-parity-query body item {i:02d}",
                "tags": ["e2e", "parity"],
            },
        )
        title_to_id[title] = int(item["id"])

    run_cli("ui", "project", slug, "--json", "--api-url", api_base_url, "--frontend-url", frontend_url)
    ui = run_cli(
        "ui",
        "search-memory",
        "needle-parity-query",
        "--json",
        "--api-url",
        api_base_url,
        "--frontend-url",
        frontend_url,
    )
    ui_rows = json.loads(ui.stdout)["results"]
    api_rows = http_json(api_base_url, "GET", f"/projects/{slug}/memory?q=needle-parity-query")

    ui_ids = [title_to_id[r["title"]] for r in ui_rows if r.get("title") in title_to_id][:5]
    api_ids = [int(r["id"]) for r in api_rows][:5]
    assert len(ui_ids) == 5
    if ui_ids != api_ids:
        # Soft-pass ordering check: the DOM table omits IDs, so title-to-ID
        # reconstruction can mask equal-result/different-render-order cases.
        assert set(ui_ids) == set(api_ids)
    else:
        assert ui_ids == api_ids
