"""Unit tests for the `agentos ui` argparse wiring.

These don't require a running browser/backend — they just exercise the
parser tree to lock in subcommand names, flag names, and exit codes.
"""

from __future__ import annotations

import argparse
import pytest

from agentos_cli.commands import ui as ui_cmd


@pytest.fixture
def parser():
    root = argparse.ArgumentParser(prog="agentos")
    sub = root.add_subparsers(dest="command")
    ui_cmd.register(sub)
    return root


def _parse(parser, argv):
    return parser.parse_args(argv)


def test_ui_subcommand_inventory(parser):
    """All spec'd subcommands must be present."""
    expected = {
        "start", "stop", "status", "logs",
        "nav", "click", "fill", "select", "press",
        "text", "html", "exists", "count", "eval", "wait",
        "url", "route", "reload", "screenshot",
        "theme", "project",
        "approve", "deny", "compile-adapters",
        "simulate-policy", "search-memory",
        "list-routes", "smoke",
    }
    # Walk parser tree: ui subparsers
    ui_sub_action = None
    for act in parser._subparsers._actions:
        if isinstance(act, argparse._SubParsersAction):
            ui_parser = act.choices.get("ui")
            assert ui_parser is not None, "ui subcommand not registered"
            for a in ui_parser._actions:
                if isinstance(a, argparse._SubParsersAction):
                    ui_sub_action = a
                    break
            break
    assert ui_sub_action is not None
    have = set(ui_sub_action.choices.keys())
    missing = expected - have
    assert not missing, f"missing subcommands: {missing}"


def test_approve_via_flags_mutually_exclusive(parser):
    args = _parse(parser, ["ui", "approve", "42", "--via-api"])
    assert args.via_api is True
    assert args.via_ui is False
    args = _parse(parser, ["ui", "approve", "42", "--via-ui"])
    assert args.via_ui is True
    assert args.via_api is False
    with pytest.raises(SystemExit):
        _parse(parser, ["ui", "approve", "42", "--via-ui", "--via-api"])


def test_deny_supports_reason(parser):
    args = _parse(parser, ["ui", "deny", "7", "--reason", "nope", "--via-api"])
    assert args.reason == "nope"
    assert args.via_api is True


def test_compile_adapters_supports_via(parser):
    args = _parse(parser, ["ui", "compile-adapters", "--via-api", "--project", "demo"])
    assert args.via_api is True
    assert args.project == "demo"


def test_logs_tail_flag(parser):
    args = _parse(parser, ["ui", "logs", "--tail", "20"])
    assert args.tail == 20


def test_route_subcommand_parses(parser):
    args = _parse(parser, ["ui", "route", "--json"])
    assert args.json is True


def test_screenshot_flags(parser):
    args = _parse(parser, [
        "ui", "screenshot", "--route", "/memory",
        "--theme", "dark", "--out", "/tmp/x.png", "--full-page",
    ])
    assert args.route == "/memory"
    assert args.theme == "dark"
    assert args.out == "/tmp/x.png"
    assert args.full_page is True


def test_exit_code_constants():
    assert ui_cmd.EXIT_OK == 0
    assert ui_cmd.EXIT_ACTION_FAILED == 1
    assert ui_cmd.EXIT_NO_SESSION == 2
    assert ui_cmd.EXIT_FRONTEND_UNREACHABLE == 3
    assert ui_cmd.EXIT_BACKEND_UNREACHABLE == 4
