"""`agentos auth-status` — CREDENTIAL-BLIND detection of Claude/Gemini/Codex CLI state.

ABSOLUTELY FORBIDDEN: opening ~/.claude/.credentials.json, ~/.codex/auth.json,
~/.config/gemini/**, or any vendor OAuth cache. We only use:
  - shutil.which(<cli>)
  - subprocess.run([<cli>, "--version"]) exit code
  - os.environ lookups for API key env vars

If you add code here, do not import anything from the filesystem reading layer
that touches those paths. The test in tests/phase1/test_auth_status.py asserts
that those file paths are NEVER opened during this command.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any

CLI_SPECS = (
    {
        "cli": "claude",
        "binary": "claude",
        "recommended_command": "claude",
        "api_key_env": ("ANTHROPIC_API_KEY",),
    },
    {
        "cli": "gemini",
        "binary": "gemini",
        "recommended_command": "gemini",
        "api_key_env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    },
    {
        "cli": "codex",
        "binary": "codex",
        "recommended_command": "codex login",
        "api_key_env": ("OPENAI_API_KEY",),
    },
)


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "auth-status",
        help="Credential-blind detection of installed AI CLIs (Claude/Gemini/Codex).",
        description=(
            "Reports install state without reading any vendor token files. "
            "Returns 'installed' if binary is on PATH and --version exits 0, "
            "'api_key_mode' if a known API-key env var is set, "
            "or 'not_installed' otherwise."
        ),
    )
    p.add_argument("--json", action="store_true", help="Emit JSON output.")
    p.set_defaults(func=_run)


def _probe_one(spec: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "cli": spec["cli"],
        "state": "not_installed",
        "recommended_command": spec["recommended_command"],
        "warnings": [],
    }

    # API-key env var check FIRST — any such var present means API-key mode
    # regardless of subscription state.
    env_set = [k for k in spec["api_key_env"] if os.environ.get(k)]
    if env_set:
        # We'll still check binary install, but state is api_key_mode.
        for k in env_set:
            result["warnings"].append(
                f"{k} set; may override subscription login"
            )

    # Binary on PATH?
    which = shutil.which(spec["binary"])
    if which is None:
        if env_set:
            result["state"] = "api_key_mode"
        else:
            result["state"] = "not_installed"
        return result

    # Probe --version with a tight timeout. Never read its stdout for tokens.
    try:
        proc = subprocess.run(
            [which, "--version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            result["state"] = "api_key_mode" if env_set else "installed"
        else:
            result["state"] = "unknown"
            result["warnings"].append(
                f"{spec['binary']} --version exited {proc.returncode}"
            )
    except subprocess.TimeoutExpired:
        result["state"] = "unknown"
        result["warnings"].append(f"{spec['binary']} --version timed out")
    except Exception as e:
        result["state"] = "unknown"
        result["warnings"].append(f"{spec['binary']} --version error: {e}")

    return result


def _run(args: argparse.Namespace) -> int:
    statuses = [_probe_one(spec) for spec in CLI_SPECS]
    if args.json:
        print(json.dumps(statuses, indent=2))
    else:
        for s in statuses:
            warn_str = (" warnings=" + ";".join(s["warnings"])) if s["warnings"] else ""
            print(f"{s['cli']:<7} state={s['state']:<14} "
                  f"recommend={s['recommended_command']}{warn_str}")
    return 0  # always 0; this is a report tool
