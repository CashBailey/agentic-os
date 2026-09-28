"""`agentos validate` — validate directory layout, templates, YAML front-matter."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentos_cli.core.templates import (
    REQUIRED_GLOBAL_CONTEXT,
    REQUIRED_GLOBAL_MEMORY,
    REQUIRED_PROJECT_CONTEXT,
    REQUIRED_PROJECT_MEMORY,
    REQUIRED_SKILLS,
    REQUIRED_TEMPLATES,
    REQUIRED_WORKFLOWS,
    parse_file,
)


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
        "validate",
        help="Validate canonical agent-os/ layout, required files, and YAML front-matter.",
    )
    p.add_argument("--project", default=None, help="Project slug to also validate.")
    p.add_argument("--json", action="store_true", help="Emit JSON output.")
    p.add_argument(
        "--agent-os-root",
        default=None,
        help="Override agent-os/ source root.",
    )
    p.set_defaults(func=_run)


def _check_file(
    root: Path, rel: str, errors: list[dict], warnings: list[dict]
) -> None:
    p = root / rel
    if not p.exists():
        errors.append({"file": rel, "line": None, "message": "missing required file"})
        return
    if not p.is_file():
        errors.append({"file": rel, "line": None, "message": "exists but is not a file"})
        return
    try:
        doc = parse_file(p)
    except Exception as e:
        errors.append({"file": rel, "line": None, "message": f"read error: {e}"})
        return
    if doc.parse_error:
        errors.append({"file": rel, "line": doc.frontmatter_lines[0] or None,
                       "message": doc.parse_error})
        return
    # Skills/workflows require front-matter with `name` + `description`.
    if rel.startswith("skills/") and rel.endswith("/SKILL.md"):
        fm = doc.frontmatter or {}
        for key in ("name", "description"):
            if key not in fm:
                errors.append({"file": rel, "line": None,
                               "message": f"skill front-matter missing '{key}'"})
    elif rel.startswith("workflows/"):
        fm = doc.frontmatter or {}
        for key in ("name", "description"):
            if key not in fm:
                errors.append({"file": rel, "line": None,
                               "message": f"workflow front-matter missing '{key}'"})


def _run(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    if args.agent_os_root:
        root = Path(args.agent_os_root).expanduser().resolve()
    else:
        root = _agent_os_root(cwd)

    if not root.is_dir():
        report = {"valid": False, "errors": [
            {"file": str(root), "line": None, "message": "agent-os/ root not initialized"}],
            "warnings": []}
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"not initialized: {root}", file=sys.stderr)
        return 2

    errors: list[dict] = []
    warnings: list[dict] = []

    required = (
        list(REQUIRED_GLOBAL_CONTEXT)
        + list(REQUIRED_GLOBAL_MEMORY)
        + list(REQUIRED_WORKFLOWS)
        + list(REQUIRED_TEMPLATES)
        + list(REQUIRED_SKILLS)
    )
    for rel in required:
        _check_file(root, rel, errors, warnings)

    # private/ README expected
    if not (root / "private" / "README.md").exists():
        warnings.append({"file": "private/README.md", "line": None,
                         "message": "missing private/ README; not fatal"})

    if args.project:
        slug = args.project
        p_ctx_dir = root / "context" / "projects" / slug
        p_mem_dir = root / "memory" / "projects" / slug
        if not p_ctx_dir.is_dir():
            errors.append({"file": f"context/projects/{slug}/", "line": None,
                           "message": "project context directory missing"})
        else:
            for f in REQUIRED_PROJECT_CONTEXT:
                _check_file(root, f"context/projects/{slug}/{f}", errors, warnings)
        if not p_mem_dir.is_dir():
            errors.append({"file": f"memory/projects/{slug}/", "line": None,
                           "message": "project memory directory missing"})
        else:
            for f in REQUIRED_PROJECT_MEMORY:
                _check_file(root, f"memory/projects/{slug}/{f}", errors, warnings)

    valid = not errors
    report = {"valid": valid, "errors": errors, "warnings": warnings}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if valid:
            print(f"OK: {root} valid"
                  + (f" (warnings: {len(warnings)})" if warnings else ""))
        else:
            print(f"INVALID: {root} ({len(errors)} errors)")
            for e in errors:
                print(f"  - {e['file']}: {e['message']}")
        for w in warnings:
            print(f"  warn: {w['file']}: {w['message']}")
    return 0 if valid else 1
