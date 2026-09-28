"""Tests for `agentos auth-status` — credential-blind invariants.

CRITICAL: auth-status MUST NOT open any vendor token file. We assert this two
ways:
  1. monkeypatch `builtins.open` to record all path accesses, then ensure the
     forbidden paths never appear.
  2. monkeypatch `pathlib.Path.read_text` / `read_bytes` similarly.
"""
from __future__ import annotations

import builtins
import io
import json
import os
import pathlib
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from agentos_cli.cli import main


FORBIDDEN_PATHS = (
    str(Path.home() / ".claude" / ".credentials.json"),
    str(Path.home() / ".codex" / "auth.json"),
    str(Path.home() / ".config" / "gemini"),
)


@pytest.fixture
def opened_paths(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every path passed to builtins.open and Path.read_*."""
    paths: list[str] = []
    real_open = builtins.open

    def spy_open(file, *args, **kwargs):
        try:
            paths.append(str(file))
        except Exception:
            pass
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_open)

    real_read_text = pathlib.Path.read_text
    real_read_bytes = pathlib.Path.read_bytes

    def spy_read_text(self, *a, **kw):
        paths.append(str(self))
        return real_read_text(self, *a, **kw)

    def spy_read_bytes(self, *a, **kw):
        paths.append(str(self))
        return real_read_bytes(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "read_text", spy_read_text)
    monkeypatch.setattr(pathlib.Path, "read_bytes", spy_read_bytes)

    return paths


def _run_capture(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_auth_status_emits_json(opened_paths: list[str]) -> None:
    rc, out = _run_capture(["auth-status", "--json"])
    assert rc == 0
    payload = json.loads(out)
    assert isinstance(payload, list)
    clis = {item["cli"] for item in payload}
    assert clis == {"claude", "gemini", "codex"}
    for item in payload:
        assert item["state"] in {"not_installed", "installed", "api_key_mode", "unknown"}


def test_auth_status_never_opens_forbidden_paths(opened_paths: list[str]) -> None:
    rc, _ = _run_capture(["auth-status", "--json"])
    assert rc == 0
    for opened in opened_paths:
        for forbidden in FORBIDDEN_PATHS:
            assert not opened.startswith(forbidden), (
                f"auth-status opened forbidden path {opened} (matches {forbidden})"
            )


def test_auth_status_reports_api_key_mode(
    monkeypatch: pytest.MonkeyPatch, opened_paths: list[str]
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    rc, out = _run_capture(["auth-status", "--json"])
    assert rc == 0
    payload = json.loads(out)
    claude = next(p for p in payload if p["cli"] == "claude")
    # Either installed+api_key_mode, or not_installed+api_key_mode hint
    assert any("ANTHROPIC_API_KEY" in w for w in claude["warnings"])


def test_auth_status_when_no_binaries(
    monkeypatch: pytest.MonkeyPatch, opened_paths: list[str]
) -> None:
    # Force shutil.which to return None for all
    import shutil as _shutil
    monkeypatch.setattr(_shutil, "which", lambda *_a, **_k: None)
    # Clear env vars
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    rc, out = _run_capture(["auth-status", "--json"])
    assert rc == 0
    payload = json.loads(out)
    for item in payload:
        assert item["state"] == "not_installed"
