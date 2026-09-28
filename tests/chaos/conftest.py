"""Shared fixtures and skip helpers for chaos tests.

Chaos tests deliberately disrupt the live stack (docker, workers, browser
daemons). Each helper here returns a (bool, reason) pair so a test can call
``pytest.skip(reason)`` with a clear, human-readable message when the host is
not capable of running it.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"

# Make the backend package importable for tests that touch app.* directly.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def docker_available() -> Tuple[bool, str]:
    """Return (True, '') iff `docker info` succeeds for the current user."""
    if shutil.which("docker") is None:
        return False, "docker CLI not installed on PATH"
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"docker info failed: {e!r}"
    if r.returncode != 0:
        # Trim noisy stderr to the first line for the skip reason.
        first = (r.stderr or r.stdout or "").splitlines()[:1]
        return False, f"docker daemon unreachable: {first[0] if first else 'no detail'}"
    return True, ""


def container_running(name: str) -> bool:
    try:
        r = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


def db_available() -> Tuple[bool, str]:
    """Return (True, '') iff SyncSessionLocal can connect."""
    if os.environ.get("SKIP_DB_TESTS"):
        return False, "SKIP_DB_TESTS is set"
    try:
        from sqlalchemy import create_engine, text  # noqa: WPS433

        from app.config import sync_database_url  # noqa: WPS433
    except Exception as e:  # pragma: no cover - import failure
        return False, f"backend not importable: {e!r}"
    try:
        eng = create_engine(sync_database_url(), future=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return True, ""
    except Exception as e:
        return False, f"postgres not reachable: {e!r}"


def backend_http_available(url: str = "http://127.0.0.1:8000/health", timeout: float = 1.0) -> bool:
    """Cheap reachability check; returns False quickly when nothing is listening."""
    try:
        import urllib.request  # noqa: WPS433

        with urllib.request.urlopen(url, timeout=timeout):  # nosec - trusted localhost
            return True
    except Exception:
        return False


def tcp_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def docker_ok() -> None:
    ok, reason = docker_available()
    if not ok:
        pytest.skip(f"docker unavailable: {reason}")


@pytest.fixture(scope="session")
def db_ok() -> None:
    ok, reason = db_available()
    if not ok:
        pytest.skip(f"db unavailable: {reason}")
