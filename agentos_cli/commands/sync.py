"""`agentos sync` — generate CLAUDE.md / GEMINI.md / AGENTS.md from canonical context."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from agentos_cli.core.context_loader import load_context, render_unified_markdown
from agentos_cli.safety.path_guard import (
    ProtectedPathError,
    assert_writable,
    DEFAULT_PROTECTED,
)
from agentos_cli.core.paths import PathTraversalError


ADAPTER_FILES = ("CLAUDE.md", "GEMINI.md", "AGENTS.md")


def _agent_os_root(start: Path) -> Path:
    """Find the agent-os/ root. Walk up from `start` looking for `agent-os/`."""
    p = start.resolve()
    while True:
        candidate = p / "agent-os"
        if candidate.is_dir():
            return candidate
        if p.parent == p:
            # default to <cwd>/agent-os even if it doesn't exist
            return start.resolve() / "agent-os"
        p = p.parent


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "sync",
        help="Generate CLAUDE.md / GEMINI.md / AGENTS.md from canonical context.",
        description="Generate adapter markdown files from the canonical agent-os/ context.",
    )
    p.add_argument("--project", default=None, help="Project slug (optional).")
    p.add_argument(
        "--target",
        default=None,
        help="Target directory to write into (default: current working directory).",
    )
    p.add_argument(
        "--mode",
        choices=("dry-run", "copy", "symlink"),
        default="dry-run",
        help="Write mode. Default 'dry-run' prints planned writes only.",
    )
    p.add_argument(
        "--backup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Create .bak.<timestamp> when overwriting (default: on).",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON output.")
    p.add_argument(
        "--agent-os-root",
        default=None,
        help="Override agent-os/ source root (default: discovered by walking up from cwd).",
    )
    p.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    target = Path(args.target).expanduser().resolve() if args.target else cwd.resolve()
    if args.agent_os_root:
        ao_root = Path(args.agent_os_root).expanduser().resolve()
    else:
        ao_root = _agent_os_root(cwd)

    if not ao_root.is_dir():
        msg = f"agent-os/ root not found at {ao_root}"
        if args.json:
            print(json.dumps({"error": msg, "mode": args.mode, "files": []}))
        else:
            print(f"error: {msg}", file=sys.stderr)
        return 1

    target.mkdir(parents=True, exist_ok=True)

    lc = load_context(ao_root, project_slug=args.project)
    content = render_unified_markdown(lc)

    files_report: list[dict] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    exit_code = 0

    for name in ADAPTER_FILES:
        dst = target / name
        action = "would-write"
        backup_path: str | None = None
        try:
            assert_writable(dst, target, DEFAULT_PROTECTED)
        except ProtectedPathError as e:
            files_report.append(
                {
                    "src": "<rendered>",
                    "target": str(dst),
                    "action": "blocked",
                    "reason": str(e),
                    "backup_path": None,
                }
            )
            exit_code = 2
            continue
        except PathTraversalError as e:
            files_report.append(
                {
                    "src": "<rendered>",
                    "target": str(dst),
                    "action": "blocked",
                    "reason": str(e),
                    "backup_path": None,
                }
            )
            exit_code = 2
            continue

        if args.mode == "dry-run":
            files_report.append(
                {
                    "src": "<rendered>",
                    "target": str(dst),
                    "action": action,
                    "backup_path": None,
                }
            )
            continue

        # copy or symlink modes — both write the same content file (symlink
        # mode for `sync` falls back to copy since we're rendering, not
        # linking. `install-adapter` honors symlink for true linking.)
        existed = dst.exists() or dst.is_symlink()
        if existed:
            if not args.backup:
                files_report.append(
                    {
                        "src": "<rendered>",
                        "target": str(dst),
                        "action": "skipped-exists",
                        "backup_path": None,
                    }
                )
                exit_code = 3
                continue
            backup_path = str(dst) + f".bak.{timestamp}"
            shutil.copy2(dst, backup_path) if dst.is_file() else None

        dst.write_text(content, encoding="utf-8")
        files_report.append(
            {
                "src": "<rendered>",
                "target": str(dst),
                "action": "wrote",
                "backup_path": backup_path,
            }
        )

    report = {"mode": args.mode, "files": files_report}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"sync mode={args.mode} target={target}")
        for f in files_report:
            print(f"  {f['action']:<14} {f['target']}"
                  + (f"  (backup: {f['backup_path']})" if f.get("backup_path") else "")
                  + (f"  -- {f.get('reason')}" if f.get("reason") else ""))
    return exit_code
