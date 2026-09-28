#!/usr/bin/env python3
"""T-SEC-001 — credential-blind detection.

Asserts:
1. `agentos auth-status` runs without opening vendor credential files
   (~/.codex/auth.json, ~/.claude/.credentials.json, ~/.config/gemini/**).
   Uses strace -e openat when available; otherwise falls back to a runtime
   monkeypatch check via the existing phase1 test.
2. Source tree contains no unguarded references to vendor token paths.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WANT_JSON = "--json" in sys.argv[1:]
AGENTOS = REPO_ROOT / ".venv" / "bin" / "agentos"
PY = REPO_ROOT / ".venv" / "bin" / "python"

FORBIDDEN_PATHS = [
    str(Path.home() / ".codex" / "auth.json"),
    str(Path.home() / ".claude" / ".credentials.json"),
    str(Path.home() / ".config" / "gemini"),
]


def emit(status: str, evidence: str) -> int:
    if WANT_JSON:
        print(json.dumps({"id": "T-SEC-001", "status": status, "evidence": evidence}))
    else:
        print(f"[T-SEC-001] {status} — {evidence}")
    return 0 if status == "PASS" else 1


def strace_check() -> tuple[bool, str]:
    if not shutil.which("strace"):
        return False, "strace-unavailable"
    try:
        proc = subprocess.run(
            ["strace", "-f", "-e", "trace=openat", "-o", "/tmp/agentos-cb.strace",
             str(AGENTOS), "auth-status"],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, "strace timed out"
    if proc.returncode != 0:
        return False, f"auth-status nonzero exit ({proc.returncode}): {proc.stderr[:120]}"
    try:
        trace = Path("/tmp/agentos-cb.strace").read_text(errors="replace")
    except OSError as e:
        return False, f"could not read strace log: {e}"
    leaked = [p for p in FORBIDDEN_PATHS if p in trace]
    if leaked:
        return False, f"vendor credentials opened: {leaked}"
    return True, "strace confirms no vendor credential openat"


def source_grep_check() -> tuple[bool, str]:
    targets = ["agentos_cli", "backend"]
    hits: list[str] = []
    for t in targets:
        d = REPO_ROOT / t
        if not d.exists():
            continue
        try:
            out = subprocess.run(
                ["grep", "-rn", "-E", "--exclude-dir=__pycache__",
                 r"auth\.json|credentials\.json", str(d)],
                capture_output=True, text=True, timeout=20,
            ).stdout
        except subprocess.TimeoutExpired:
            return False, "grep timed out"
        for line in out.splitlines():
            # path_guard.py and auth_status.py declare these as DENY/FORBIDDEN sets.
            if "safety/path_guard.py" in line or "services/auth_status.py" in line:
                continue
            lower = line.lower()
            if any(k in lower for k in ("must not", "never", "forbidden", "protected",
                                        "allow", "deny", "blind", "do not", "refuse")):
                continue
            hits.append(line)
    if hits:
        return False, f"unguarded vendor-token references: {hits[:3]}"
    return True, "no unguarded vendor-token references in source"


def main() -> int:
    ok1, ev1 = strace_check()
    if not ok1:
        # Fallback to the phase1 credential-blind test if strace is unavailable.
        if ev1 == "strace-unavailable":
            test_path = REPO_ROOT / "tests" / "phase1"
            env = {**os.environ}
            env.pop("PYTHONPATH", None)
            proc = subprocess.run(
                [str(PY), "-m", "pytest", str(test_path), "-q", "-k", "blind or credential"],
                capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120,
            )
            if proc.returncode != 0:
                return emit("FAIL", f"fallback pytest credential-blind failed: {proc.stdout[-200:]}")
            ev1 = "fallback pytest credential-blind PASS"
        else:
            return emit("FAIL", ev1)

    ok2, ev2 = source_grep_check()
    if not ok2:
        return emit("FAIL", ev2)
    return emit("PASS", f"{ev1}; {ev2}")


if __name__ == "__main__":
    sys.exit(main())
