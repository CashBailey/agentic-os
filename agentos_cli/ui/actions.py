"""Low-level Playwright primitives for the UI CLI.

Every function here accepts an already-attached Playwright Page (acquired
via :func:`agentos_cli.ui.session.page_context`) so callers (CLI handlers,
shortcuts, smoke runner) control scoping.

Selectors accept Playwright's full locator grammar — CSS, ``text=...``,
``role=...``, chains like ``role=row >> text="#7"`` — without modification.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import selectors as S
from .session import (
    SCREENSHOT_DIR,
    resolve_url,
    slugify_route,
)


class UIActionError(Exception):
    """Raised when a primitive fails (selector miss, timeout, navigation error)."""


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def nav(page, frontend_url: str, route_or_url: str, *, timeout_ms: int = 15_000) -> str:
    """Navigate; return the final URL after load."""
    url = resolve_url(frontend_url, route_or_url)
    try:
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    except Exception as e:
        raise UIActionError(f"navigate to {url} failed: {e}") from e
    # Wait for the SPA shell so subsequent selectors aren't racing hydration.
    try:
        page.wait_for_selector(S.APP_SHELL_HEADER, timeout=timeout_ms, state="attached")
    except Exception:
        # Non-fatal — return the URL anyway. Callers can decide.
        pass
    return page.url


def reload(page, *, timeout_ms: int = 15_000) -> str:
    page.reload(timeout=timeout_ms, wait_until="domcontentloaded")
    return page.url


def url(page) -> str:
    return page.url


# ---------------------------------------------------------------------------
# Elements
# ---------------------------------------------------------------------------

def _locator(page, selector: str):
    """Build a Playwright Locator from a free-form selector string."""
    return page.locator(selector)


def click(page, selector: str, *, timeout_ms: int = 10_000) -> None:
    try:
        _locator(page, selector).first.click(timeout=timeout_ms)
    except Exception as e:
        raise UIActionError(f"click {selector!r} failed: {e}") from e


def fill(page, selector: str, value: str, *, timeout_ms: int = 10_000) -> None:
    try:
        _locator(page, selector).first.fill(value, timeout=timeout_ms)
    except Exception as e:
        raise UIActionError(f"fill {selector!r} failed: {e}") from e


def select_option(page, selector: str, value: str, *, timeout_ms: int = 10_000) -> list[str]:
    try:
        return _locator(page, selector).first.select_option(value=value, timeout=timeout_ms)
    except Exception as e:
        raise UIActionError(f"select {selector!r} = {value!r} failed: {e}") from e


def press(page, key: str) -> None:
    try:
        page.keyboard.press(key)
    except Exception as e:
        raise UIActionError(f"press {key!r} failed: {e}") from e


def text(page, selector: str, *, timeout_ms: int = 10_000) -> str:
    try:
        return _locator(page, selector).first.inner_text(timeout=timeout_ms)
    except Exception as e:
        raise UIActionError(f"text {selector!r} failed: {e}") from e


def html(page, selector: str, *, timeout_ms: int = 10_000) -> str:
    try:
        return _locator(page, selector).first.evaluate("el => el.outerHTML", timeout=timeout_ms)
    except Exception as e:
        raise UIActionError(f"html {selector!r} failed: {e}") from e


def exists(page, selector: str, *, timeout_ms: int = 1_500) -> bool:
    """True if at least one element matches and is attached within timeout."""
    try:
        loc = _locator(page, selector).first
        loc.wait_for(state="attached", timeout=timeout_ms)
        return True
    except Exception:
        return False


def count(page, selector: str) -> int:
    try:
        return _locator(page, selector).count()
    except Exception as e:
        raise UIActionError(f"count {selector!r} failed: {e}") from e


def eval_js(page, expression: str) -> Any:
    """Evaluate a JS expression in the page; result must be JSON-serialisable."""
    # Wrap expression so callers can pass either ``foo()`` (an expression) or
    # a function source ``() => foo()`` — Playwright handles both, but we
    # explicitly accept the bare expression form.
    try:
        return page.evaluate(expression)
    except Exception as e:
        raise UIActionError(f"eval {expression!r} failed: {e}") from e


def wait(
    page,
    selector: str,
    *,
    timeout_ms: int = 10_000,
    state: str = "visible",
) -> None:
    try:
        _locator(page, selector).first.wait_for(state=state, timeout=timeout_ms)
    except Exception as e:
        raise UIActionError(f"wait {selector!r} state={state} failed: {e}") from e


# ---------------------------------------------------------------------------
# Screenshots
# ---------------------------------------------------------------------------

def screenshot(
    page,
    *,
    out: Optional[Path] = None,
    selector: Optional[str] = None,
    full_page: bool = False,
    route_for_naming: Optional[str] = None,
    theme_for_naming: Optional[str] = None,
    timeout_ms: int = 15_000,
) -> Path:
    """Take a screenshot and write to disk; return the absolute path."""
    if out is None:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = slugify_route(route_for_naming or page.url.split("//", 1)[-1].split("/", 1)[-1] or "root")
        theme_part = f"-{theme_for_naming}" if theme_for_naming else ""
        out = SCREENSHOT_DIR / f"{slug}{theme_part}-{ts}.png"
    else:
        out = Path(out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

    try:
        if selector:
            _locator(page, selector).first.screenshot(path=str(out), timeout=timeout_ms)
        else:
            page.screenshot(path=str(out), full_page=full_page, timeout=timeout_ms)
    except Exception as e:
        raise UIActionError(f"screenshot failed: {e}") from e
    return out.resolve()


# ---------------------------------------------------------------------------
# Theme & project introspection (cheap helpers used by `status`)
# ---------------------------------------------------------------------------

def current_theme(page) -> Optional[str]:
    try:
        v = page.evaluate("document.documentElement.getAttribute('data-theme')")
        return v if v in ("dark", "light") else None
    except Exception:
        return None


def current_route(page) -> str:
    try:
        return page.evaluate("window.location.pathname")
    except Exception:
        return ""
