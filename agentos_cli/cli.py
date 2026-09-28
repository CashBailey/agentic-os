"""Root argparse CLI with auto-discovery of `agentos_cli.commands.*` modules.

Each command module MUST expose a `register(subparsers)` function that adds its
subparser and sets `func=<handler>` where handler receives the parsed args
namespace and returns an int exit code.
"""
from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys
from typing import Optional, Sequence


def _discover_and_register(subparsers: argparse._SubParsersAction) -> list[str]:
    """Import every submodule of agentos_cli.commands and call register()."""
    import agentos_cli.commands as commands_pkg

    registered: list[str] = []
    for modinfo in pkgutil.iter_modules(commands_pkg.__path__):
        if modinfo.name.startswith("_"):
            continue
        full_name = f"{commands_pkg.__name__}.{modinfo.name}"
        try:
            mod = importlib.import_module(full_name)
        except Exception as e:  # pragma: no cover - defensive
            print(f"warning: failed to import {full_name}: {e}", file=sys.stderr)
            continue
        reg = getattr(mod, "register", None)
        if not callable(reg):
            continue
        try:
            reg(subparsers)
            registered.append(modinfo.name)
        except Exception as e:  # pragma: no cover - defensive
            print(f"warning: register() failed for {full_name}: {e}", file=sys.stderr)
    return registered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentos",
        description="Agentic OS CLI — sync/validate/auth-status/install-adapter (+ compile-adapters in phase 2).",
    )
    parser.add_argument("--version", action="version", version="agentos 0.1.0")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    _discover_and_register(subparsers)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 0
    try:
        rc = func(args)
    except SystemExit as e:
        return int(e.code or 0)
    return int(rc or 0)


if __name__ == "__main__":
    raise SystemExit(main())
