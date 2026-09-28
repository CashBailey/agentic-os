"""Credential-blind invariant: auth_status service must NEVER open vendor token files."""

from __future__ import annotations

import builtins
import io
import os

import pytest

from app.services.auth_status import _FORBIDDEN_PATHS, get_auth_status


def test_no_forbidden_path_is_opened(monkeypatch):
    opened: list[str] = []
    real_open = builtins.open

    def guarded_open(file, *args, **kwargs):  # type: ignore[no-untyped-def]
        path = os.fspath(file) if not isinstance(file, int) else ""
        for forbidden in _FORBIDDEN_PATHS:
            if path == forbidden or path.startswith(forbidden + os.sep):
                opened.append(path)
                raise AssertionError(
                    f"auth_status tried to open forbidden vendor path: {path}"
                )
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    # Should run without touching forbidden files.
    out = get_auth_status()
    assert opened == []
    assert isinstance(out, list)
    assert {entry["cli"] for entry in out} == {"claude", "gemini", "codex"}
    for entry in out:
        assert entry["state"] in {"not_installed", "installed", "api_key_mode", "unknown"}
