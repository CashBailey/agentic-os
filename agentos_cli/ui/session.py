"""Persistent browser daemon for the Agentic OS UI CLI.

Architecture
------------
`agentos ui start` spawns the Playwright-managed Chromium binary directly
with `--remote-debugging-port=0` (kernel picks a port), detached via
`start_new_session=True`, in headless or headed mode. We tail its stderr for
the `DevTools listening on ws://...` line, parse the websocket endpoint,
and persist it to ``/tmp/agentos-ui/session.json`` alongside the PID,
frontend URL, API URL, and start time. Every subsequent command (nav,
click, screenshot, ...) calls :func:`attach_or_oneshot`, which connects to
that websocket via Playwright's ``connect_over_cdp``.

If no daemon is running, the same helpers fall back to a one-shot headless
launch using ``sync_playwright().chromium.launch()`` — convenient for ad-hoc
``agentos ui screenshot --route /``.

State files
-----------
``/tmp/agentos-ui/``:
  session.json   — {pid, ws_endpoint, http_endpoint, frontend_url, api_url, started_at, headed}
  browser.pid    — PID of the Chromium process (for crash recovery / kill -0)
  browser.log    — combined stderr/stdout from the daemon
  vite.pid       — written by `ui ensure-frontend`
  screenshots/   — default destination for `ui screenshot`
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# Paths & defaults
# ---------------------------------------------------------------------------

STATE_DIR = Path("/tmp/agentos-ui")
SESSION_FILE = STATE_DIR / "session.json"
BROWSER_PID_FILE = STATE_DIR / "browser.pid"
BROWSER_LOG_FILE = STATE_DIR / "browser.log"
VITE_PID_FILE = STATE_DIR / "vite.pid"
SCREENSHOT_DIR = STATE_DIR / "screenshots"

DEFAULT_FRONTEND_URL = "http://localhost:5173"
DEFAULT_API_URL = "http://127.0.0.1:8765"

# Where playwright stashes the chromium binary.
def _chromium_executable() -> str:
    """Find the chromium / headless-shell binary Playwright downloaded.

    Falls back to whatever ``sync_playwright().chromium.executable_path``
    reports, but we resolve lazily to avoid importing Playwright at module
    import time (CLI startup latency).
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # executable_path is a property on BrowserType.
        return p.chromium.executable_path


# ---------------------------------------------------------------------------
# State dataclass
# ---------------------------------------------------------------------------

@dataclass
class SessionInfo:
    pid: int
    ws_endpoint: str
    http_endpoint: str
    frontend_url: str
    api_url: str
    started_at: str
    headed: bool

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't own it.
        return True
    return True


def read_session() -> Optional[SessionInfo]:
    if not SESSION_FILE.exists():
        return None
    try:
        d = json.loads(SESSION_FILE.read_text())
        return SessionInfo(**d)
    except Exception:
        return None


def write_session(info: SessionInfo) -> None:
    _ensure_state_dir()
    SESSION_FILE.write_text(json.dumps(info.to_dict(), indent=2))


def clear_session() -> None:
    for p in (SESSION_FILE, BROWSER_PID_FILE):
        with contextlib.suppress(FileNotFoundError):
            p.unlink()


def session_is_live() -> Optional[SessionInfo]:
    """Return a SessionInfo if the recorded daemon is still running, else None."""
    info = read_session()
    if not info:
        return None
    if not _pid_alive(info.pid):
        return None
    return info


# ---------------------------------------------------------------------------
# Daemon launch
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"DevTools listening on (ws://\S+)")


def _wait_for_ws(log_path: Path, timeout: float = 25.0) -> Optional[str]:
    """Tail ``log_path`` until we see ``DevTools listening on ws://…`` or time out."""
    deadline = time.monotonic() + timeout
    seen = ""
    while time.monotonic() < deadline:
        try:
            seen = log_path.read_text(errors="replace")
        except FileNotFoundError:
            seen = ""
        m = _WS_RE.search(seen)
        if m:
            return m.group(1)
        time.sleep(0.1)
    return None


def _ws_to_http(ws: str) -> str:
    """ws://host:port/devtools/browser/... -> http://host:port"""
    rest = ws[len("ws://"):]
    host_port = rest.split("/", 1)[0]
    return f"http://{host_port}"


def start_daemon(
    *,
    headed: bool = False,
    frontend_url: str = DEFAULT_FRONTEND_URL,
    api_url: str = DEFAULT_API_URL,
) -> SessionInfo:
    """Spawn a detached Chromium with a CDP endpoint and record it.

    Raises RuntimeError on failure to come up.
    """
    _ensure_state_dir()

    existing = session_is_live()
    if existing:
        return existing

    chromium = _chromium_executable()
    if not chromium or not Path(chromium).exists():
        raise RuntimeError(
            f"chromium binary not found at {chromium!r}; run "
            "`.venv/bin/playwright install chromium`."
        )

    # Use a per-session profile so multiple daemons could be supported later.
    profile_dir = STATE_DIR / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Truncate the log so _wait_for_ws sees a fresh DevTools line.
    BROWSER_LOG_FILE.write_text("")

    args = [
        chromium,
        f"--user-data-dir={profile_dir}",
        "--remote-debugging-port=0",
        # Many Linux hosts (Ubuntu 23.10+ AppArmor, container, CI) disallow
        # the chromium user-namespace sandbox. We run as a developer tool
        # against trusted local origins, so disable it unconditionally.
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate,BackForwardCache,AcceptCHFrame,MediaRouter,OptimizationHints",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-sync",
    ]
    if not headed:
        args.append("--headless=new")
    # Pre-open the frontend so screenshots etc. don't always need a nav.
    args.append(frontend_url)

    log_fh = BROWSER_LOG_FILE.open("ab", buffering=0)
    proc = subprocess.Popen(
        args,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )

    ws = _wait_for_ws(BROWSER_LOG_FILE, timeout=25.0)
    if not ws:
        # Daemon never produced a websocket; kill it and surface the log tail.
        with contextlib.suppress(ProcessLookupError):
            os.kill(proc.pid, signal.SIGTERM)
        tail = ""
        with contextlib.suppress(Exception):
            tail = BROWSER_LOG_FILE.read_text()[-2000:]
        raise RuntimeError(
            "chromium daemon failed to expose a CDP endpoint within 25s.\n"
            f"--- last 2KB of {BROWSER_LOG_FILE} ---\n{tail}"
        )

    BROWSER_PID_FILE.write_text(str(proc.pid))
    info = SessionInfo(
        pid=proc.pid,
        ws_endpoint=ws,
        http_endpoint=_ws_to_http(ws),
        frontend_url=frontend_url,
        api_url=api_url,
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        headed=headed,
    )
    write_session(info)
    return info


def stop_daemon() -> bool:
    """Kill the recorded daemon. Returns True if a process was signalled."""
    info = read_session()
    killed = False
    if info and _pid_alive(info.pid):
        with contextlib.suppress(ProcessLookupError):
            os.kill(info.pid, signal.SIGTERM)
        # Give it 3s, then SIGKILL.
        for _ in range(30):
            if not _pid_alive(info.pid):
                break
            time.sleep(0.1)
        if _pid_alive(info.pid):
            with contextlib.suppress(ProcessLookupError):
                os.kill(info.pid, signal.SIGKILL)
        killed = True
    clear_session()
    return killed


# ---------------------------------------------------------------------------
# Vite (frontend dev server) helpers
# ---------------------------------------------------------------------------

def _http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 400
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError):
        return False


def ensure_frontend(port: int = 5173, timeout: float = 30.0) -> dict:
    """Start `npm run dev` in frontend/ if the port isn't already serving."""
    _ensure_state_dir()
    url = f"http://localhost:{port}"
    if _http_ok(url + "/"):
        return {"status": "already-running", "url": url}

    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "frontend"
    if not frontend_dir.is_dir():
        return {"status": "error", "error": f"frontend dir not found at {frontend_dir}"}

    npm = shutil.which("npm")
    if not npm:
        return {"status": "error", "error": "npm not on PATH"}

    log = STATE_DIR / "vite.log"
    log_fh = log.open("ab", buffering=0)
    proc = subprocess.Popen(
        [npm, "run", "dev", "--", "--port", str(port)],
        cwd=str(frontend_dir),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    VITE_PID_FILE.write_text(str(proc.pid))

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _http_ok(url + "/"):
            return {"status": "started", "url": url, "pid": proc.pid, "log": str(log)}
        if proc.poll() is not None:
            return {
                "status": "error",
                "error": f"npm exited with {proc.returncode}; see {log}",
            }
        time.sleep(0.4)
    return {"status": "error", "error": f"timeout after {timeout}s waiting for {url}"}


# ---------------------------------------------------------------------------
# Page acquisition (the thing actions.py calls)
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def page_context(
    *,
    frontend_url: str = DEFAULT_FRONTEND_URL,
    api_url: str = DEFAULT_API_URL,
    require_daemon: bool = False,
) -> Iterator[tuple[object, object]]:
    """Yield ``(page, info)`` connected to the daemon if running, else one-shot.

    ``info`` is a SessionInfo (live or synthetic). The yielded ``page`` is
    a Playwright sync ``Page`` — its first existing browser tab if a daemon
    is attached, or a freshly opened blank tab on a one-shot launch.

    On daemon attach we DO NOT close the browser on exit (it's persistent).
    On one-shot we close everything we opened.
    """
    from playwright.sync_api import sync_playwright

    info = session_is_live()
    pw = sync_playwright().start()

    browser = None
    context = None
    page = None
    daemon = info is not None
    try:
        if daemon:
            browser = pw.chromium.connect_over_cdp(info.ws_endpoint)
            # Reuse the first existing context+page if present, else create.
            if browser.contexts:
                context = browser.contexts[0]
            else:
                context = browser.new_context()
            if context.pages:
                page = context.pages[0]
            else:
                page = context.new_page()
            yield page, info
        else:
            if require_daemon:
                raise RuntimeError("no daemon running (use `agentos ui start`)")
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            synthetic = SessionInfo(
                pid=os.getpid(),
                ws_endpoint="",
                http_endpoint="",
                frontend_url=frontend_url,
                api_url=api_url,
                started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                headed=False,
            )
            yield page, synthetic
    finally:
        try:
            if not daemon:
                # One-shot cleanup.
                with contextlib.suppress(Exception):
                    if context is not None:
                        context.close()
                with contextlib.suppress(Exception):
                    if browser is not None:
                        browser.close()
            else:
                # Daemon stays alive; just disconnect this client.
                with contextlib.suppress(Exception):
                    if browser is not None:
                        browser.close()
        finally:
            with contextlib.suppress(Exception):
                pw.stop()


def resolve_url(frontend_url: str, route_or_url: str) -> str:
    """Return an absolute URL: pass-through if absolute, else join with frontend_url."""
    if route_or_url.startswith("http://") or route_or_url.startswith("https://"):
        return route_or_url
    if not route_or_url.startswith("/"):
        route_or_url = "/" + route_or_url
    return frontend_url.rstrip("/") + route_or_url


def slugify_route(route: str) -> str:
    s = route.strip("/").replace("/", "_") or "root"
    # Strip query/hash if any.
    s = s.split("?", 1)[0].split("#", 1)[0]
    return re.sub(r"[^a-zA-Z0-9_-]", "-", s)
