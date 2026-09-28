"""`agentos compile-adapters` — phase 2 CLI subcommand."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentos_cli.core.adapter_compiler import (
    AdapterSpecError,
    compile_all,
)
from agentos_cli.core.policy import PolicyError


def _agent_os_root(start: Path) -> Path:
    """Find the agent-os/ directory by walking up from `start`."""
    p = start.resolve()
    while True:
        candidate = p / "agent-os"
        if candidate.is_dir():
            return candidate
        if p.parent == p:
            return start.resolve() / "agent-os"
        p = p.parent


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "compile-adapters",
        help="Compile tool-neutral policies into per-CLI adapter outputs.",
        description=(
            "Read agent-os/policies/*.yaml + agent-os/adapters/*.yaml + canonical "
            "context and write agent-os/generated/{claude,gemini,codex}/** "
            "deterministically."
        ),
    )
    p.add_argument("--project", default=None, help="Project slug (optional).")
    p.add_argument(
        "--check",
        action="store_true",
        help="Validate inputs and render outputs in memory without writing.",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON output.")
    p.add_argument(
        "--agent-os-root",
        default=None,
        help="Override agent-os/ root (default: discovered from cwd).",
    )
    p.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    if args.agent_os_root:
        ao_root = Path(args.agent_os_root).expanduser().resolve()
    else:
        ao_root = _agent_os_root(cwd)

    if not ao_root.is_dir():
        msg = f"agent-os/ root not found at {ao_root}"
        _emit_error(args, msg, exit_code=1)
        return 1

    try:
        report = compile_all(
            agent_os_root=ao_root,
            project_slug=args.project,
            check_only=bool(args.check),
        )
    except PolicyError as e:
        _emit_error(args, f"policy error: {e}", exit_code=1)
        return 1
    except AdapterSpecError as e:
        _emit_error(args, f"adapter spec error: {e}", exit_code=2)
        return 2

    if args.json:
        out = report.to_dict()
        out["check_only"] = bool(args.check)
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        mode = "check" if args.check else "write"
        print(f"compile-adapters mode={mode} agent_os={ao_root}")
        print(f"source_hash={report.source_hash}")
        for r in report.results:
            status = "would-write" if args.check else ("wrote" if r.written else "skipped")
            print(f"  [{r.cli:<6}] {status} ({len(r.files)} files)")
            for f in r.files:
                print(f"    - {f['path']}  ({f['bytes']}B)")
    return 0


def _emit_error(args: argparse.Namespace, msg: str, exit_code: int) -> None:
    if args.json:
        print(json.dumps({"error": msg, "exit_code": exit_code}))
    else:
        print(f"error: {msg}", file=sys.stderr)
