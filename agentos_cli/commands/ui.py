"""`agentos ui` — CLI control plane for the React frontend.

Registers a hierarchical subcommand: every browser-driven action (nav,
click, fill, screenshot, theme toggle, approve, ...) is reachable from the
shell so that testing never depends on hand-driven clicks.

The implementation lives in :mod:`agentos_cli.ui` (session/actions/
shortcuts/smoke); this file is only the argparse wiring.
"""

from __future__ import annotations

import argparse
import json as _json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

# Lazy imports so `agentos --help` doesn't pay the Playwright import tax.


# ---------------------------------------------------------------------------
# Exit codes (per spec)
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_ACTION_FAILED = 1
EXIT_NO_SESSION = 2
EXIT_FRONTEND_UNREACHABLE = 3
EXIT_BACKEND_UNREACHABLE = 4


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _emit(args: argparse.Namespace, human: str, payload: dict | list | str | int | bool | None) -> None:
    if getattr(args, "json", False):
        print(_json.dumps(payload, indent=2, default=str))
    else:
        print(human)


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Page-context helpers (DRY for handlers)
# ---------------------------------------------------------------------------

def _with_page(args: argparse.Namespace, fn: Callable, *, require_daemon: bool = False) -> Any:
    """Run ``fn(page, info)`` inside a session.page_context.

    Returns whatever fn returns (or raises). Caller maps exceptions → exit codes.
    """
    from agentos_cli.ui.session import page_context, DEFAULT_FRONTEND_URL, DEFAULT_API_URL

    frontend_url = getattr(args, "frontend_url", None) or DEFAULT_FRONTEND_URL
    api_url = getattr(args, "api_url", None) or DEFAULT_API_URL
    with page_context(
        frontend_url=frontend_url,
        api_url=api_url,
        require_daemon=require_daemon,
    ) as (page, info):
        return fn(page, info)


def _handle(args: argparse.Namespace, fn: Callable, *, require_daemon: bool = False) -> int:
    try:
        return fn(args) if require_daemon is None else fn(args)
    except Exception:  # pragma: no cover - defensive
        traceback.print_exc()
        return EXIT_ACTION_FAILED


# ===========================================================================
# Handlers
# ===========================================================================

# --- Session lifecycle -----------------------------------------------------

def _h_start(args: argparse.Namespace) -> int:
    from agentos_cli.ui.session import (
        DEFAULT_API_URL,
        DEFAULT_FRONTEND_URL,
        start_daemon,
    )

    try:
        info = start_daemon(
            headed=bool(args.headed),
            frontend_url=args.frontend_url or DEFAULT_FRONTEND_URL,
            api_url=args.api_url or DEFAULT_API_URL,
        )
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, f"started pid={info.pid} ws={info.ws_endpoint}", info.to_dict())
    return EXIT_OK


def _h_stop(args: argparse.Namespace) -> int:
    from agentos_cli.ui.session import stop_daemon

    killed = stop_daemon()
    _emit(args, "stopped" if killed else "no session", {"killed": killed})
    return EXIT_OK


def _h_status(args: argparse.Namespace) -> int:
    from agentos_cli.ui.session import session_is_live

    info = session_is_live()
    if not info:
        _emit(args, "no session", {"running": False})
        return EXIT_OK

    # Best-effort: attach briefly to read route + theme.
    route, theme = None, None
    try:
        from agentos_cli.ui.session import page_context
        from agentos_cli.ui import actions as A

        with page_context(frontend_url=info.frontend_url, api_url=info.api_url) as (page, _):
            route = A.current_route(page)
            theme = A.current_theme(page)
    except Exception:
        pass

    payload = info.to_dict()
    payload.update({"running": True, "route": route, "theme": theme})
    _emit(
        args,
        f"running pid={info.pid} url={info.frontend_url} route={route} theme={theme}",
        payload,
    )
    return EXIT_OK


def _h_ensure_frontend(args: argparse.Namespace) -> int:
    from agentos_cli.ui.session import ensure_frontend

    res = ensure_frontend(port=args.port)
    if res.get("status") == "error":
        _err(res.get("error", "unknown error"))
        _emit(args, "frontend unreachable", res)
        return EXIT_FRONTEND_UNREACHABLE
    _emit(args, f"{res['status']} {res.get('url', '')}", res)
    return EXIT_OK


# --- Low-level primitives --------------------------------------------------

def _h_nav(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        final = A.nav(page, info.frontend_url, args.route)
        return final

    try:
        final = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, final, {"url": final})
    return EXIT_OK


def _h_click(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        A.click(page, args.selector)
        return page.url

    try:
        url = _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, "clicked", {"ok": True, "selector": args.selector, "url": url})
    return EXIT_OK


def _h_fill(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        A.fill(page, args.selector, args.value)

    try:
        _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, "filled", {"ok": True, "selector": args.selector, "value": args.value})
    return EXIT_OK


def _h_select(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        return A.select_option(page, args.selector, args.value)

    try:
        chosen = _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, ", ".join(chosen), {"ok": True, "selected": chosen})
    return EXIT_OK


def _h_press(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        A.press(page, args.key)

    try:
        _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, "pressed", {"ok": True, "key": args.key})
    return EXIT_OK


def _h_text(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        return A.text(page, args.selector)

    try:
        t = _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, t, {"text": t})
    return EXIT_OK


def _h_html(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        return A.html(page, args.selector)

    try:
        h = _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, h, {"html": h})
    return EXIT_OK


def _h_exists(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        return A.exists(page, args.selector, timeout_ms=args.timeout)

    found = _with_page(args, _run)
    _emit(args, "yes" if found else "no", {"exists": bool(found)})
    return EXIT_OK if found else EXIT_ACTION_FAILED


def _h_count(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        return A.count(page, args.selector)

    try:
        n = _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, str(n), {"count": n})
    return EXIT_OK


def _h_eval(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        return A.eval_js(page, args.expression)

    try:
        v = _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, _json.dumps(v, default=str), {"value": v})
    return EXIT_OK


def _h_wait(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        A.wait(page, args.selector, timeout_ms=args.timeout, state=args.state)

    try:
        _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, "ok", {"ok": True, "selector": args.selector, "state": args.state})
    return EXIT_OK


def _h_url(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        return A.url(page)

    u = _with_page(args, _run)
    _emit(args, u, {"url": u})
    return EXIT_OK


def _h_reload(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        return A.reload(page)

    u = _with_page(args, _run)
    _emit(args, u, {"url": u})
    return EXIT_OK


def _h_route(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A

    def _run(page, info):
        return A.current_route(page)

    try:
        r = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, r or "", {"route": r})
    return EXIT_OK


def _h_logs(args: argparse.Namespace) -> int:
    from agentos_cli.ui.session import BROWSER_LOG_FILE

    if not BROWSER_LOG_FILE.exists():
        _emit(args, "", {"lines": [], "path": str(BROWSER_LOG_FILE)})
        return EXIT_OK
    lines = BROWSER_LOG_FILE.read_text(errors="replace").splitlines()
    n = getattr(args, "tail", None)
    if n:
        lines = lines[-int(n):]
    if getattr(args, "json", False):
        print(_json.dumps({"path": str(BROWSER_LOG_FILE), "lines": lines}, default=str))
    else:
        for line in lines:
            print(line)
    return EXIT_OK


# --- Screenshot ------------------------------------------------------------

def _h_screenshot(args: argparse.Namespace) -> int:
    from agentos_cli.ui import actions as A
    from agentos_cli.ui import shortcuts as SC

    def _run(page, info):
        if args.route:
            A.nav(page, info.frontend_url, args.route)
        if args.theme:
            SC.set_theme(page, args.theme)
        out = Path(args.out).expanduser().resolve() if args.out else None
        return A.screenshot(
            page,
            out=out,
            selector=args.selector,
            full_page=bool(args.full_page),
            route_for_naming=args.route,
            theme_for_naming=args.theme,
        )

    try:
        path = _with_page(args, _run)
    except A.UIActionError as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, str(path), {"path": str(path)})
    return EXIT_OK


# --- High-level shortcuts --------------------------------------------------

def _h_theme(args: argparse.Namespace) -> int:
    from agentos_cli.ui import shortcuts as SC

    def _run(page, info):
        return SC.set_theme(page, args.target)

    try:
        res = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, f"{res['before']} -> {res['after']}", res)
    return EXIT_OK if res["ok"] else EXIT_ACTION_FAILED


def _h_project(args: argparse.Namespace) -> int:
    from agentos_cli.ui import shortcuts as SC

    def _run(page, info):
        return SC.set_project(page, args.slug)

    try:
        res = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, f"{res['before']} -> {res['after']}", res)
    return EXIT_OK if res["ok"] else EXIT_ACTION_FAILED


def _via_choice(args: argparse.Namespace) -> str:
    """Resolve --via-ui / --via-api / default to 'ui'."""
    if getattr(args, "via_api", False):
        return "api"
    if getattr(args, "via_ui", False):
        return "ui"
    return "ui"


def _h_approve(args: argparse.Namespace) -> int:
    from agentos_cli.ui import shortcuts as SC
    from agentos_cli.ui.session import DEFAULT_API_URL, DEFAULT_FRONTEND_URL

    fe = args.frontend_url or DEFAULT_FRONTEND_URL
    api = args.api_url or DEFAULT_API_URL
    if not SC.ping_backend(api):
        _err(f"backend not reachable at {api}")
        return EXIT_BACKEND_UNREACHABLE

    via = _via_choice(args)
    if via == "api":
        try:
            res = SC.approve_via_api(args.id, api_url=api)
        except Exception as e:
            _err(str(e))
            return EXIT_ACTION_FAILED
        res["via"] = "api"
        _emit(args, f"#{args.id} -> {res.get('backend_status')} (api)", res)
        return EXIT_OK if res["ok"] else EXIT_ACTION_FAILED

    def _run(page, info):
        return SC.approve(page, args.id, frontend_url=fe, api_url=api)

    try:
        res = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    res["via"] = "ui"
    _emit(args, f"#{args.id} -> {res.get('backend_status')} (ui)", res)
    return EXIT_OK if res["ok"] else EXIT_ACTION_FAILED


def _h_deny(args: argparse.Namespace) -> int:
    from agentos_cli.ui import shortcuts as SC
    from agentos_cli.ui.session import DEFAULT_API_URL, DEFAULT_FRONTEND_URL

    fe = args.frontend_url or DEFAULT_FRONTEND_URL
    api = args.api_url or DEFAULT_API_URL
    if not SC.ping_backend(api):
        _err(f"backend not reachable at {api}")
        return EXIT_BACKEND_UNREACHABLE

    via = _via_choice(args)
    if via == "api":
        try:
            res = SC.deny_via_api(args.id, api_url=api, reason=args.reason)
        except Exception as e:
            _err(str(e))
            return EXIT_ACTION_FAILED
        res["via"] = "api"
        _emit(args, f"#{args.id} -> {res.get('backend_status')} (api)", res)
        return EXIT_OK if res["ok"] else EXIT_ACTION_FAILED

    def _run(page, info):
        return SC.deny(page, args.id, frontend_url=fe, api_url=api, reason=args.reason)

    try:
        res = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    res["via"] = "ui"
    _emit(args, f"#{args.id} -> {res.get('backend_status')} (ui)", res)
    return EXIT_OK if res["ok"] else EXIT_ACTION_FAILED


def _h_compile_adapters(args: argparse.Namespace) -> int:
    from agentos_cli.ui import shortcuts as SC
    from agentos_cli.ui.session import DEFAULT_API_URL, DEFAULT_FRONTEND_URL

    fe = args.frontend_url or DEFAULT_FRONTEND_URL
    api = args.api_url or DEFAULT_API_URL
    via = _via_choice(args)
    if via == "api":
        if not SC.ping_backend(api):
            _err(f"backend not reachable at {api}")
            return EXIT_BACKEND_UNREACHABLE
        try:
            res = SC.compile_adapters_via_api(api_url=api, project_slug=getattr(args, "project", None))
        except Exception as e:
            _err(str(e))
            return EXIT_ACTION_FAILED
        res["via"] = "api"
        _emit(args, f"compile-adapters ok={res['ok']} (api)", res)
        return EXIT_OK if res["ok"] else EXIT_ACTION_FAILED

    def _run(page, info):
        return SC.compile_adapters(page, frontend_url=fe)

    try:
        res = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    res["via"] = "ui"
    _emit(args, f"compile-adapters ok={res['ok']} (ui)", res)
    return EXIT_OK if res["ok"] else EXIT_ACTION_FAILED


def _h_simulate_policy(args: argparse.Namespace) -> int:
    from agentos_cli.ui import shortcuts as SC
    from agentos_cli.ui.session import DEFAULT_FRONTEND_URL

    fe = args.frontend_url or DEFAULT_FRONTEND_URL

    def _run(page, info):
        return SC.simulate_policy(
            page,
            tool=args.tool,
            action=args.action,
            args_json=args.args,
            frontend_url=fe,
        )

    try:
        res = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, f"decision={res.get('decision')} matched_rule={res.get('matched_rule')}", res)
    return EXIT_OK if res["ok"] else EXIT_ACTION_FAILED


def _h_search_memory(args: argparse.Namespace) -> int:
    from agentos_cli.ui import shortcuts as SC
    from agentos_cli.ui.session import DEFAULT_FRONTEND_URL

    fe = args.frontend_url or DEFAULT_FRONTEND_URL

    def _run(page, info):
        return SC.search_memory(
            page,
            query=args.query,
            semantic=bool(args.semantic),
            frontend_url=fe,
        )

    try:
        res = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    _emit(args, f"{len(res['results'])} rows", res)
    return EXIT_OK


def _h_list_routes(args: argparse.Namespace) -> int:
    from agentos_cli.ui import shortcuts as SC

    routes = SC.list_routes()
    if getattr(args, "json", False):
        print(_json.dumps(routes))
    else:
        for r in routes:
            print(r)
    return EXIT_OK


# --- Smoke -----------------------------------------------------------------

def _h_smoke(args: argparse.Namespace) -> int:
    from agentos_cli.ui import smoke as SM
    from agentos_cli.ui.session import DEFAULT_API_URL, DEFAULT_FRONTEND_URL

    fe = args.frontend_url or DEFAULT_FRONTEND_URL
    api = args.api_url or DEFAULT_API_URL

    def _run(page, info):
        return SM.run_smoke(page, frontend_url=fe, api_url=api)

    try:
        report = _with_page(args, _run)
    except Exception as e:
        _err(str(e))
        return EXIT_ACTION_FAILED
    ok = bool(report.get("ok"))
    if getattr(args, "json", False):
        print(_json.dumps(report, indent=2, default=str))
    else:
        print(f"smoke ok={ok} routes={report['routes_checked']} themes=2 shots={report['screenshots_taken']}")
        print(f"  report: {report.get('report_path')}")
        for r in report.get("results", []):
            mark = "OK " if r.get("ok") else "FAIL"
            print(f"  [{mark}] {r.get('theme'):<5} {r.get('route'):<12} {r.get('screenshot', '')}")
    return EXIT_OK if ok else EXIT_ACTION_FAILED


# ===========================================================================
# Argparse wiring
# ===========================================================================

def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="Emit JSON output.")
    p.add_argument("--frontend-url", default=None, help="Override frontend URL.")
    p.add_argument("--api-url", default=None, help="Override backend API URL.")


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "ui",
        help="CLI control of the React frontend (Playwright-backed).",
        description="CLI parity for everything controllable in the browser.",
    )
    sub = p.add_subparsers(dest="ui_command", metavar="<subcommand>", required=False)

    # --- Lifecycle --------------------------------------------------------
    s = sub.add_parser("start", help="Launch persistent browser daemon.")
    _add_common(s)
    s.add_argument("--headed", action="store_true", help="Open a visible window.")
    s.set_defaults(func=_h_start)

    s = sub.add_parser("stop", help="Kill the persistent browser daemon.")
    _add_common(s)
    s.set_defaults(func=_h_stop)

    s = sub.add_parser("status", help="Report daemon status / current route / theme.")
    _add_common(s)
    s.set_defaults(func=_h_status)

    s = sub.add_parser("ensure-frontend", help="Start `npm run dev` if not already serving.")
    _add_common(s)
    s.add_argument("--port", type=int, default=5173)
    s.set_defaults(func=_h_ensure_frontend)

    # --- Low-level primitives --------------------------------------------
    s = sub.add_parser("nav", help="Navigate to route or URL.")
    _add_common(s)
    s.add_argument("route", help="/route or absolute URL.")
    s.set_defaults(func=_h_nav)

    s = sub.add_parser("click", help="Click an element by Playwright selector.")
    _add_common(s)
    s.add_argument("selector")
    s.set_defaults(func=_h_click)

    s = sub.add_parser("fill", help="Fill an input.")
    _add_common(s)
    s.add_argument("selector")
    s.add_argument("value")
    s.set_defaults(func=_h_fill)

    s = sub.add_parser("select", help="Choose an <option> by value.")
    _add_common(s)
    s.add_argument("selector")
    s.add_argument("value")
    s.set_defaults(func=_h_select)

    s = sub.add_parser("press", help="Press a keyboard key (Enter, Escape, ...).")
    _add_common(s)
    s.add_argument("key")
    s.set_defaults(func=_h_press)

    s = sub.add_parser("text", help="Print visible text of an element.")
    _add_common(s)
    s.add_argument("selector")
    s.set_defaults(func=_h_text)

    s = sub.add_parser("html", help="Print outerHTML of an element.")
    _add_common(s)
    s.add_argument("selector")
    s.set_defaults(func=_h_html)

    s = sub.add_parser("exists", help="Exit 0 if element present, 1 if not.")
    _add_common(s)
    s.add_argument("selector")
    s.add_argument("--timeout", type=int, default=1_500, help="ms")
    s.set_defaults(func=_h_exists)

    s = sub.add_parser("count", help="Print integer count of matches.")
    _add_common(s)
    s.add_argument("selector")
    s.set_defaults(func=_h_count)

    s = sub.add_parser("eval", help="Evaluate a JS expression in page context.")
    _add_common(s)
    s.add_argument("expression")
    s.set_defaults(func=_h_eval)

    s = sub.add_parser("wait", help="Wait for an element / state.")
    _add_common(s)
    s.add_argument("selector")
    s.add_argument("--timeout", type=int, default=10_000, help="ms")
    s.add_argument(
        "--state",
        choices=("visible", "attached", "hidden", "detached"),
        default="visible",
    )
    s.set_defaults(func=_h_wait)

    s = sub.add_parser("url", help="Print current page URL.")
    _add_common(s)
    s.set_defaults(func=_h_url)

    s = sub.add_parser("reload", help="Reload the current page.")
    _add_common(s)
    s.set_defaults(func=_h_reload)

    s = sub.add_parser("route", help="Print current page pathname (e.g. /memory).")
    _add_common(s)
    s.set_defaults(func=_h_route)

    s = sub.add_parser("logs", help="Print/tail the persistent browser daemon log.")
    _add_common(s)
    s.add_argument("--tail", type=int, default=None, help="Only print last N lines.")
    s.set_defaults(func=_h_logs)

    # --- Screenshot -------------------------------------------------------
    s = sub.add_parser("screenshot", help="Capture a PNG screenshot.")
    _add_common(s)
    s.add_argument("--route", default=None, help="Navigate here first.")
    s.add_argument("--selector", default=None, help="Screenshot just this element.")
    s.add_argument("--out", default=None, help="Output path (default auto).")
    s.add_argument("--full-page", action="store_true", help="Capture beyond viewport.")
    s.add_argument("--theme", choices=("dark", "light"), default=None,
                   help="Flip theme via UI toggle before capture.")
    s.set_defaults(func=_h_screenshot)

    # --- High-level shortcuts --------------------------------------------
    s = sub.add_parser("theme", help="Set or toggle theme via the UI button.")
    _add_common(s)
    s.add_argument("target", choices=("dark", "light", "toggle"))
    s.set_defaults(func=_h_theme)

    s = sub.add_parser("project", help="Choose project from top-bar switcher.")
    _add_common(s)
    s.add_argument("slug")
    s.set_defaults(func=_h_project)

    def _add_via(p_: argparse.ArgumentParser) -> None:
        grp = p_.add_mutually_exclusive_group()
        grp.add_argument("--via-ui", action="store_true",
                         help="Drive the actual UI button (default).")
        grp.add_argument("--via-api", action="store_true",
                         help="Hit the backend endpoint directly (fast path).")

    s = sub.add_parser("approve", help="Approve an approval row.")
    _add_common(s)
    _add_via(s)
    s.add_argument("id", type=int)
    s.set_defaults(func=_h_approve)

    s = sub.add_parser("deny", help="Deny an approval row.")
    _add_common(s)
    _add_via(s)
    s.add_argument("id", type=int)
    s.add_argument("--reason", default=None)
    s.set_defaults(func=_h_deny)

    s = sub.add_parser("compile-adapters", help="Click 'Compile now' on /adapters.")
    _add_common(s)
    _add_via(s)
    s.add_argument("--project", default=None, help="Project slug (api path only).")
    s.set_defaults(func=_h_compile_adapters)

    s = sub.add_parser("simulate-policy", help="Run the /policies simulator form.")
    _add_common(s)
    s.add_argument("--tool", required=True)
    s.add_argument("--action", required=True)
    s.add_argument("--args", required=True, help="JSON string for args.")
    s.set_defaults(func=_h_simulate_policy)

    s = sub.add_parser("search-memory", help="Search /memory and return rows.")
    _add_common(s)
    s.add_argument("query")
    s.add_argument("--semantic", action="store_true")
    s.set_defaults(func=_h_search_memory)

    s = sub.add_parser("list-routes", help="Print known SPA routes.")
    _add_common(s)
    s.set_defaults(func=_h_list_routes)

    # --- Smoke ------------------------------------------------------------
    s = sub.add_parser("smoke", help="Exercise every route in both themes; write JSON report.")
    _add_common(s)
    s.set_defaults(func=_h_smoke)

    # If user types just `agentos ui`, print help.
    def _default(_args: argparse.Namespace) -> int:
        p.print_help()
        return EXIT_OK

    p.set_defaults(func=_default)
