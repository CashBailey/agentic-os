"""`agentos install-adapter` — install generated adapter files into a target repo.

Installs both the top-level instruction MD (CLAUDE.md / GEMINI.md / AGENTS.md)
AND the per-CLI subtree directory (`.claude/`, `.gemini/`, `.codex/`) into the
target repo. Per-file path safety, backup, and dry-run all apply uniformly.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from agentos_cli.core.context_loader import load_context, render_unified_markdown
from agentos_cli.core.paths import PathTraversalError
from agentos_cli.safety.path_guard import (
    DEFAULT_PROTECTED,
    ProtectedPathError,
    assert_writable,
)

# CLI -> (top-level MD filename, source subtree dir name, target subtree dir name)
CLI_LAYOUT = {
    "claude": ("CLAUDE.md", "claude", ".claude"),
    "gemini": ("GEMINI.md", "gemini", ".gemini"),
    "codex": ("AGENTS.md", "codex", ".codex"),
}


def _agent_os_root(start: Path) -> Path:
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
        "install-adapter",
        help="Install generated CLAUDE.md/GEMINI.md/AGENTS.md + per-CLI subtrees into a target repo.",
    )
    p.add_argument("--project", default=None)
    p.add_argument(
        "--target",
        required=True,
        help="Target repo root.",
    )
    p.add_argument(
        "--mode",
        choices=("dry-run", "copy", "symlink"),
        default="dry-run",
    )
    p.add_argument("--backup", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--cli",
        choices=("claude", "gemini", "codex", "all"),
        default="all",
    )
    p.add_argument("--json", action="store_true")
    p.add_argument("--agent-os-root", default=None)
    p.set_defaults(func=_run)


def _install_one_file(
    src: Path,
    dst: Path,
    target_root: Path,
    mode: str,
    backup: bool,
    timestamp: str,
    files_report: list[dict],
) -> int:
    """Install a single file. Returns 0 on ok, or an exit_code delta (2|3) on issue.

    Always appends exactly one entry to files_report.
    """
    # Path safety on dst — must be within target root and not match protected globs.
    try:
        assert_writable(dst, target_root, DEFAULT_PROTECTED)
    except (ProtectedPathError, PathTraversalError) as e:
        files_report.append({
            "src": str(src),
            "target": str(dst),
            "action": "blocked",
            "reason": str(e),
            "backup_path": None,
        })
        return 2

    if mode == "dry-run":
        files_report.append({
            "src": str(src),
            "target": str(dst),
            "action": "would-write",
            "backup_path": None,
        })
        return 0

    backup_path = None
    if dst.exists() or dst.is_symlink():
        if not backup:
            files_report.append({
                "src": str(src),
                "target": str(dst),
                "action": "skipped-exists",
                "backup_path": None,
            })
            return 3
        backup_path = str(dst) + f".bak.{timestamp}"
        if dst.is_symlink() or dst.is_file():
            os.replace(dst, backup_path)
        elif dst.is_dir():
            # Defensive: should not happen for per-file installs; skip.
            files_report.append({
                "src": str(src),
                "target": str(dst),
                "action": "skipped-is-dir",
                "backup_path": None,
            })
            return 3

    dst.parent.mkdir(parents=True, exist_ok=True)

    if mode == "symlink":
        # Per-file symlinks (predictable; never per-directory).
        os.symlink(src.resolve(), dst)
    else:
        shutil.copy2(src, dst)

    files_report.append({
        "src": str(src),
        "target": str(dst),
        "action": "wrote",
        "backup_path": backup_path,
    })
    return 0


def _run(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
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

    target = Path(args.target).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    clis = ("claude", "gemini", "codex") if args.cli == "all" else (args.cli,)

    lc = load_context(ao_root, project_slug=args.project)
    content = render_unified_markdown(lc)

    # Write rendered content to generated/ staging files so symlink mode has
    # something to link to. Subtree files are expected to already exist from a
    # prior `agentos compile-adapters` run.
    gen_dir = ao_root / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)

    files_report: list[dict] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    exit_code = 0

    for cli in clis:
        fname, src_subdir_name, dst_subdir_name = CLI_LAYOUT[cli]

        # ---- 1. Top-level MD file -------------------------------------------------
        top_src = gen_dir / fname
        top_dst = target / fname

        # Ensure the staging MD exists / is refreshed (only meaningful for copy+symlink,
        # but harmless in dry-run too — keeps generated/ deterministic).
        if args.mode != "dry-run":
            top_src.write_text(content, encoding="utf-8")

        rc = _install_one_file(
            top_src, top_dst, target, args.mode, args.backup, timestamp, files_report
        )
        if rc:
            exit_code = max(exit_code, rc)

        # ---- 2. Per-CLI subtree ---------------------------------------------------
        src_subtree = gen_dir / src_subdir_name
        dst_subtree = target / dst_subdir_name

        if not src_subtree.is_dir():
            files_report.append({
                "src": str(src_subtree),
                "target": str(dst_subtree),
                "action": "skipped-no-source",
                "reason": f"source subtree not found; run `agentos compile-adapters` first",
                "backup_path": None,
            })
            continue

        # Walk subtree, install per-file preserving relative paths.
        for src_file in sorted(src_subtree.rglob("*")):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(src_subtree)
            dst_file = dst_subtree / rel
            rc = _install_one_file(
                src_file, dst_file, target, args.mode, args.backup, timestamp, files_report
            )
            if rc:
                exit_code = max(exit_code, rc)

    report = {"mode": args.mode, "files": files_report}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"install-adapter mode={args.mode} target={target}")
        for f in files_report:
            extra = ""
            if f.get("backup_path"):
                extra += f"  (backup: {f['backup_path']})"
            if f.get("reason"):
                extra += f"  -- {f['reason']}"
            print(f"  {f['action']:<18} {f['target']}{extra}")
    return exit_code
