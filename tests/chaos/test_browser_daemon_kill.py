"""Chaos: SIGKILL the chromium daemon; assert the CLI auto-recovers.

After ``agentos ui start``, we read the daemon PID from
``/tmp/agentos-ui/browser.pid`` (see ``agentos_cli/ui/session.py``) and
SIGKILL it. The next CLI invocation
must either return a clean status (recognising the daemon is gone and
treating the session as stopped) or be able to restart the daemon without
manual intervention.

Skips when ``.venv/bin/agentos`` is missing or chromium is not installed
(``ui start`` exits non-zero).
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTOS_BIN = REPO_ROOT / ".venv" / "bin" / "agentos"
STATE_DIR = REPO_ROOT / "agentos_cli" / "ui" / ".state"
BROWSER_PID_FILE = STATE_DIR / "browser.pid"


def _run(*args: str, timeout: float = 60.0) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [str(AGENTOS_BIN), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


@pytest.fixture
def stop_daemon_after():
    yield
    try:
        _run("ui", "stop", timeout=30.0)
    except Exception:
        pass


def test_browser_daemon_sigkill_auto_recovers(stop_daemon_after) -> None:
    if not AGENTOS_BIN.exists():
        pytest.skip(f"agentos CLI not found at {AGENTOS_BIN}")

    start = _run("ui", "start", timeout=60.0)
    if start.returncode != 0:
        pytest.skip(
            "agentos ui start failed (chromium not installed?); "
            f"stderr={start.stderr.strip()[:200]}"
        )

    # Read the daemon PID.
    deadline = time.monotonic() + 10.0
    pid = -1
    while time.monotonic() < deadline:
        if BROWSER_PID_FILE.exists():
            try:
                pid = int(BROWSER_PID_FILE.read_text().strip())
                if _pid_alive(pid):
                    break
            except ValueError:
                pass
        time.sleep(0.2)
    assert pid > 0 and _pid_alive(pid), (
        f"chromium daemon PID not alive after `ui start` (pid={pid})"
    )

    # SIGKILL the chromium daemon.
    os.kill(pid, signal.SIGKILL)
    # Wait for the OS to reap it.
    for _ in range(30):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    assert not _pid_alive(pid), f"chromium pid {pid} still alive after SIGKILL"

    # CLI must auto-recover: status should succeed; or, failing that, a fresh
    # `ui start` must succeed (proving the CLI cleaned up stale state).
    status = _run("ui", "status", timeout=20.0)
    if status.returncode == 0:
        return

    restart = _run("ui", "start", timeout=60.0)
    assert restart.returncode == 0, (
        "neither `ui status` nor `ui start` recovered after SIGKILL;\n"
        f"status.stdout={status.stdout[:300]!r}\n"
        f"status.stderr={status.stderr[:300]!r}\n"
        f"restart.stdout={restart.stdout[:300]!r}\n"
        f"restart.stderr={restart.stderr[:300]!r}"
    )
