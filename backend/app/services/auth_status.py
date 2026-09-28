"""Credential-blind detection of Claude / Gemini / Codex CLI presence.

INVARIANT: this module NEVER reads vendor token caches. The only signals
allowed are: ``which <cli>`` (binary presence), ``<cli> --version`` (runnable
state), and the presence of API-key env vars. Any attempt to open a path in
:data:`_FORBIDDEN_PATHS` is a contract violation.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

# Documented guard: these paths must NEVER be opened by this module.
# Tests monkeypatch ``builtins.open`` to assert no forbidden path is touched.
_FORBIDDEN_PATHS = frozenset(
    {
        os.path.expanduser("~/.codex/auth.json"),
        os.path.expanduser("~/.claude/.credentials.json"),
        os.path.expanduser("~/.config/gemini"),
    }
)


_CLIS = (
    ("claude", "claude", ("ANTHROPIC_API_KEY",)),
    ("gemini", "gemini", ("GEMINI_API_KEY", "GOOGLE_API_KEY")),
    ("codex", "codex login", ("OPENAI_API_KEY",)),
)


def _runnable(binary: str) -> bool:
    try:
        proc = subprocess.run(
            [binary, "--version"],
            shell=False,
            check=False,
            capture_output=True,
            timeout=5,
            env=os.environ.copy(),
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def get_auth_status() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cli, recommended, key_envs in _CLIS:
        warnings: list[str] = []
        binary = shutil.which(cli)
        if binary is None:
            state = "not_installed"
        else:
            runnable = _runnable(binary)
            env_set = [k for k in key_envs if os.environ.get(k)]
            if env_set:
                state = "api_key_mode"
                for k in env_set:
                    warnings.append(
                        f"{k} set; may override subscription login"
                    )
            else:
                state = "installed" if runnable else "unknown"
        out.append(
            {
                "cli": cli,
                "state": state,
                "recommended_command": recommended,
                "warnings": warnings,
            }
        )
    return out
