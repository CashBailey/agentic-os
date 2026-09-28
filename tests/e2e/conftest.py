"""Pytest E2E fixtures for the live AgenticOS stack.

Run with:
    pytest -p no:launch_testing -p no:launch_ros tests/e2e/ -v --tb=short
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

import pytest

REPO_ROOT = Path("/home/raptor-lab-laptop2/AgenticOS/agentic-os")
PROBES = REPO_ROOT / "verification" / "probes"
EVIDENCE_ROOT = REPO_ROOT / "verification" / "results" / "e2e"


def pytest_configure(config: pytest.Config) -> None:
    for marker in ["e2e", *(f"e2e_{i:03d}" for i in range(1, 9))]:
        config.addinivalue_line("markers", f"{marker}: AgenticOS E2E scenario")


def agentos_bin() -> str:
    env_bin = os.environ.get("AGENTOS_BIN")
    if env_bin:
        return env_bin
    venv_bin = REPO_ROOT / ".venv" / "bin" / "agentos"
    if venv_bin.exists():
        return str(venv_bin)
    return shutil.which("agentos") or "agentos"


def http_json(
    base_url: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw = res.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def approval_by_id(api_base_url: str, approval_id: int) -> dict[str, Any]:
    for row in http_json(api_base_url, "GET", "/approvals"):
        if int(row["id"]) == int(approval_id):
            return row
    raise AssertionError(f"approval id={approval_id} not found")


def create_approval(api_base_url: str, project_slug: str, tag: str) -> dict[str, Any]:
    return http_json(
        api_base_url,
        "POST",
        "/approvals",
        {
            "project_slug": project_slug,
            "tool": "shell",
            "action": f"echo {tag}",
            "raw_input": {"cmd": f"echo {tag}"},
            "normalized": {"cmd": f"echo {tag}"},
            "risk": "low",
            "agent_reason": "e2e",
            "policy_reason": "e2e",
            "ttl_seconds": 600,
        },
    )


def release_and_execute(api_base_url: str, approval_id: int) -> dict[str, Any]:
    rel = http_json(api_base_url, "POST", f"/approvals/{approval_id}/release")
    return http_json(
        api_base_url,
        "POST",
        f"/approvals/{approval_id}/execute",
        {"release_token": rel["release_token"], "execution_result": {"ok": True}},
    )


def audit_events(
    api_base_url: str, project_slug: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    suffix = f"?limit={limit}"
    if project_slug:
        suffix += f"&project={project_slug}"
    rows = http_json(api_base_url, "GET", f"/audit{suffix}")["items"]
    return sorted(rows, key=lambda e: int(e["id"]))


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return os.environ.get("AGENTOS_API_BASE", "http://127.0.0.1:8765")


@pytest.fixture(scope="session")
def frontend_url() -> str:
    return os.environ.get("AGENTOS_FRONTEND_URL", "http://127.0.0.1:5173")


@pytest.fixture(scope="session")
def backend_running(api_base_url: str) -> None:
    try:
        http_json(api_base_url, "GET", "/healthz", timeout=2.0)
    except (OSError, urllib.error.URLError) as exc:
        pytest.skip(f"backend not running at {api_base_url}/healthz: {exc}")


@pytest.fixture
def tmp_project(api_base_url: str, backend_running: None, tmp_path: Path) -> dict[str, Any]:
    slug = f"e2e-{int(time.time() * 1000)}-{os.getpid()}-{tmp_path.name}"
    return http_json(
        api_base_url,
        "POST",
        "/projects",
        {"slug": slug, "name": f"E2E {slug}", "root_path": str(tmp_path)},
    )


@pytest.fixture(scope="session")
def ui_session(api_base_url: str, frontend_url: str, backend_running: None) -> dict[str, Any]:
    if not shutil.which(agentos_bin()) and not Path(agentos_bin()).exists():
        pytest.skip("agentos command not on PATH")
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"playwright not importable: {exc}")

    start = subprocess.run(
        [
            agentos_bin(),
            "ui",
            "start",
            "--json",
            "--api-url",
            api_base_url,
            "--frontend-url",
            frontend_url,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=45,
    )
    if start.returncode != 0:
        pytest.skip(f"agentos ui start failed: {start.stderr or start.stdout}")
    yield json.loads(start.stdout or "{}")
    subprocess.run(
        [agentos_bin(), "ui", "stop", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.fixture
def evidence_dir(request: pytest.FixtureRequest) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.nodeid)
    path = EVIDENCE_ROOT / f"{time.strftime('%Y%m%d-%H%M%S')}-{safe}"
    setattr(request.node, "_e2e_evidence_dir", path)
    return path


@pytest.fixture
def run_probe(request: pytest.FixtureRequest, api_base_url: str) -> Callable[..., dict[str, Any]]:
    def _run(name: str, *extra: str, check: bool = True, timeout: int = 60) -> dict[str, Any]:
        probe = PROBES / name
        cmd = [sys.executable, str(probe)] if probe.suffix == ".py" else ["bash", str(probe)]
        env = {**os.environ, "AGENTOS_API_BASE": api_base_url}
        proc = subprocess.run(
            [*cmd, *extra, "--json"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        logs = getattr(request.node, "_e2e_probe_logs", [])
        logs.append((name, proc.stdout, proc.stderr, proc.returncode))
        setattr(request.node, "_e2e_probe_logs", logs)
        if check and proc.returncode != 0:
            raise AssertionError(f"{name} failed rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}")
        line = next((ln for ln in reversed(proc.stdout.splitlines()) if ln.strip()), "{}")
        return json.loads(line)

    return _run


@pytest.fixture
def run_cli(
    request: pytest.FixtureRequest, api_base_url: str, frontend_url: str
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def _run(*args: str, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "AGENTOS_API_BASE": api_base_url,
            "AGENTOS_FRONTEND_URL": frontend_url,
        }
        proc = subprocess.run(
            [agentos_bin(), *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        logs = getattr(request.node, "_e2e_cli_logs", [])
        logs.append((" ".join(args), proc.stdout, proc.stderr, proc.returncode))
        setattr(request.node, "_e2e_cli_logs", logs)
        if check and proc.returncode != 0:
            raise AssertionError(f"agentos {' '.join(args)} failed rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}")
        return proc

    return _run


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    path = getattr(item, "_e2e_evidence_dir", None)
    if path is None:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", item.nodeid)
        path = EVIDENCE_ROOT / f"{time.strftime('%Y%m%d-%H%M%S')}-{safe}"
    path.mkdir(parents=True, exist_ok=True)
    for prefix, attr in (("probe", "_e2e_probe_logs"), ("cli", "_e2e_cli_logs")):
        for i, (name, out, err, rc) in enumerate(getattr(item, attr, []), start=1):
            (path / f"{prefix}-{i}.log").write_text(
                f"name={name}\nrc={rc}\n\nSTDOUT\n{out}\n\nSTDERR\n{err}\n",
                encoding="utf-8",
            )
    shot = path / "failure.png"
    subprocess.run(
        [agentos_bin(), "ui", "screenshot", "--out", str(shot), "--full-page"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    browser_log = Path("/tmp/agentos-ui/browser.log")
    if browser_log.exists():
        shutil.copy2(browser_log, path / "browser.log")
