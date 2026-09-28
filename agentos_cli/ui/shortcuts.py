"""High-level UI shortcuts (theme, project, approve, simulate, ...).

Each shortcut accepts an attached Playwright Page plus the parameters it
needs and returns a JSON-friendly dict describing what happened. All
shortcuts are intentionally chatty in the dict (before/after values) so
the CLI ``--json`` mode can confirm state changes.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from . import actions as A
from . import selectors as S


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

def set_theme(page, target: str, *, timeout_ms: int = 5_000) -> dict:
    """Set theme to 'dark'/'light' or toggle. Uses the actual UI button.

    target ∈ {'dark', 'light', 'toggle'}.
    """
    if target not in ("dark", "light", "toggle"):
        raise ValueError(f"target must be dark/light/toggle, got {target!r}")
    before = A.current_theme(page) or "unknown"

    if target == "toggle":
        A.click(page, S.THEME_TOGGLE, timeout_ms=timeout_ms)
    else:
        # Click the toggle until data-theme matches the desired value. The
        # toggle only flips, so at most one click is needed.
        if before != target:
            A.click(page, S.THEME_TOGGLE, timeout_ms=timeout_ms)

    # Wait for the data-theme attribute to update (React effect runs next tick).
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    after = before
    while time.monotonic() < deadline:
        after = A.current_theme(page) or "unknown"
        if target == "toggle":
            if after != before:
                break
        else:
            if after == target:
                break
        time.sleep(0.05)

    ok = (after != before) if target == "toggle" else (after == target)
    return {"before": before, "after": after, "target": target, "ok": ok}


# ---------------------------------------------------------------------------
# Project switcher
# ---------------------------------------------------------------------------

def set_project(page, slug: str, *, timeout_ms: int = 5_000) -> dict:
    """Choose a project from the top-bar <select>. Returns before/after."""
    A.wait(page, S.PROJECT_SELECT, timeout_ms=timeout_ms, state="attached")
    before = page.evaluate(f"document.querySelector({S.PROJECT_SELECT!r}).value")
    A.select_option(page, S.PROJECT_SELECT, slug, timeout_ms=timeout_ms)
    # Verify via DOM rather than Zustand internals.
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    after = before
    while time.monotonic() < deadline:
        after = page.evaluate(f"document.querySelector({S.PROJECT_SELECT!r}).value")
        if after == slug:
            break
        time.sleep(0.05)
    return {"before": before, "after": after, "target": slug, "ok": after == slug}


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

def _decide_via_ui(
    page,
    approval_id: int,
    decision: str,
    *,
    frontend_url: str,
    api_url: str,
    timeout_ms: int = 10_000,
) -> dict:
    assert decision in ("approved", "denied")
    A.nav(page, frontend_url, "/approvals", timeout_ms=timeout_ms)
    # Make sure the row is in the DOM.
    row_sel = S.approval_row(approval_id)
    try:
        A.wait(page, row_sel, timeout_ms=timeout_ms, state="visible")
    except A.UIActionError as e:
        return {
            "ok": False,
            "error": f"row #{approval_id} not visible: {e}",
            "id": approval_id,
            "decision": decision,
        }
    btn = (
        S.approve_button_css(approval_id)
        if decision == "approved"
        else S.deny_button_css(approval_id)
    )
    A.click(page, btn, timeout_ms=timeout_ms)

    # Poll backend for the new status.
    final = _poll_approval_status(api_url, approval_id, expected=decision, timeout_s=10.0)
    return {
        "ok": final == decision,
        "id": approval_id,
        "decision": decision,
        "backend_status": final,
    }


def approve(page, approval_id: int, *, frontend_url: str, api_url: str) -> dict:
    return _decide_via_ui(page, approval_id, "approved", frontend_url=frontend_url, api_url=api_url)


def _decide_via_api(approval_id: int, decision: str, *, api_url: str,
                    reason: Optional[str] = None) -> dict:
    """POST /approvals/{id}/decide and poll for the new status."""
    assert decision in ("approved", "denied")
    url = f"{api_url.rstrip('/')}/approvals/{approval_id}/decide"
    body = {"decision": decision}
    if reason:
        body["reason"] = reason
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as r:
            r.read()
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "id": approval_id,
            "decision": decision,
            "error": f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}",
        }
    final = _poll_approval_status(api_url, approval_id, expected=decision, timeout_s=10.0)
    return {
        "ok": final == decision or (decision == "approved" and final in ("released", "executed")),
        "id": approval_id,
        "decision": decision,
        "backend_status": final,
    }


def approve_via_api(approval_id: int, *, api_url: str) -> dict:
    return _decide_via_api(approval_id, "approved", api_url=api_url)


def deny_via_api(approval_id: int, *, api_url: str, reason: Optional[str] = None) -> dict:
    res = _decide_via_api(approval_id, "denied", api_url=api_url, reason=reason)
    if reason:
        res["reason"] = reason
    return res


def compile_adapters_via_api(*, api_url: str, project_slug: Optional[str] = None) -> dict:
    """Trigger adapter compile via backend endpoint.

    Tries common endpoint shapes; falls back to enqueuing a worker task.
    """
    base = api_url.rstrip("/")
    # First try project-scoped endpoint.
    candidates = []
    if project_slug:
        candidates.append(f"{base}/projects/{project_slug}/adapters/compile")
    candidates.extend([
        f"{base}/adapters/compile",
        f"{base}/compile-adapters",
    ])
    last_err = None
    for url in candidates:
        try:
            req = urllib.request.Request(
                url, data=b"{}",
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=10.0) as r:
                body = r.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {"raw": body}
            return {"ok": True, "endpoint": url, "response": payload}
        except urllib.error.HTTPError as e:
            last_err = f"{url}: HTTP {e.code}"
            if e.code in (404, 405):
                continue
            return {"ok": False, "error": last_err}
        except (urllib.error.URLError, OSError) as e:
            last_err = f"{url}: {e}"
            continue
    return {"ok": False, "error": last_err or "no compile endpoint reachable"}


def deny(page, approval_id: int, *, frontend_url: str, api_url: str, reason: str | None = None) -> dict:
    # Reason is not collected by the current UI; record it in the result.
    res = _decide_via_ui(page, approval_id, "denied", frontend_url=frontend_url, api_url=api_url)
    if reason:
        res["reason"] = reason
    return res


def _poll_approval_status(api_url: str, approval_id: int, expected: str, timeout_s: float) -> Optional[str]:
    """Poll GET /approvals until the row with id=approval_id reaches expected (or timeout)."""
    deadline = time.monotonic() + timeout_s
    last_status: Optional[str] = None
    url = f"{api_url.rstrip('/')}/approvals"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as r:
                rows = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            time.sleep(0.3)
            continue
        for row in rows:
            if row.get("id") == approval_id:
                last_status = row.get("status")
                # Both "approved" and downstream "released"/"executed" count.
                if expected == "approved" and last_status in ("approved", "released", "executed"):
                    return last_status
                if expected == "denied" and last_status == "denied":
                    return last_status
                break
        time.sleep(0.3)
    return last_status


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

def compile_adapters(page, *, frontend_url: str, timeout_ms: int = 15_000) -> dict:
    A.nav(page, frontend_url, "/adapters", timeout_ms=timeout_ms)
    A.wait(page, S.COMPILE_ADAPTERS_BUTTON, timeout_ms=timeout_ms, state="visible")
    A.click(page, S.COMPILE_ADAPTERS_BUTTON, timeout_ms=timeout_ms)
    # The mutation pushes an info notification "Compile enqueued". Use it as
    # the success signal.
    try:
        A.wait(page, 'text="Compile enqueued"', timeout_ms=timeout_ms, state="visible")
        ok, signal = True, "Compile enqueued"
    except A.UIActionError:
        # Fall back: button returns to "Compile now" once mutation settles.
        try:
            A.wait(page, 'button:has-text("Compile now")', timeout_ms=timeout_ms, state="visible")
            ok, signal = True, "button-reset"
        except A.UIActionError as e:
            return {"ok": False, "error": str(e)}
    return {"ok": ok, "signal": signal}


# ---------------------------------------------------------------------------
# Policies simulator
# ---------------------------------------------------------------------------

def simulate_policy(
    page,
    *,
    tool: str,
    action: str,
    args_json: str,
    frontend_url: str,
    timeout_ms: int = 10_000,
) -> dict:
    A.nav(page, frontend_url, "/policies", timeout_ms=timeout_ms)
    # The three inputs in the simulator card live under the "Simulate decision"
    # card. Locate them by label-following-input proximity.
    sim_card = 'div:has(> div > div >> text="Simulate decision")'
    A.wait(page, S.POLICY_SIMULATE_BUTTON, timeout_ms=timeout_ms, state="visible")
    # Inputs in DOM order under the simulator card.
    inputs = page.locator('label:has-text("tool") ~ input, label:has-text("action") ~ input, label:has-text("args (JSON)") ~ input')
    # Fallback: use ordinal locators relative to the Simulate button's card.
    page.fill('label:has-text("tool") + input, label:text("tool") + input', tool) if page.locator('label:has-text("tool") + input').count() else None
    # The Input component renders <input>; sibling selector `+` works because
    # label and input are siblings in the same wrapper div.
    page.locator('label:has-text("tool") + input').first.fill(tool, timeout=timeout_ms)
    page.locator('label:has-text("action") + input').first.fill(action, timeout=timeout_ms)
    page.locator('label:has-text("args (JSON)") + input').first.fill(args_json, timeout=timeout_ms)
    A.click(page, S.POLICY_SIMULATE_BUTTON, timeout_ms=timeout_ms)

    # Result card shows "decision" and "matched_rule" labels with values.
    # We poll the DOM for the appearance of either decision badge.
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    decision_val: Optional[str] = None
    matched_rule: Optional[str] = None
    while time.monotonic() < deadline:
        try:
            decision_val = page.evaluate(
                """() => {
                    const labels = [...document.querySelectorAll('div')].filter(
                        d => d.textContent && d.textContent.trim().toLowerCase() === 'decision'
                    );
                    for (const lab of labels) {
                        const parent = lab.parentElement;
                        if (!parent) continue;
                        const badge = parent.querySelector('span,div');
                        const txt = parent.innerText.split('\\n').map(s => s.trim()).filter(Boolean);
                        // last token after 'decision' is the value
                        const idx = txt.findIndex(t => t.toLowerCase() === 'decision');
                        if (idx >= 0 && idx + 1 < txt.length) return txt[idx + 1];
                    }
                    return null;
                }"""
            )
            matched_rule = page.evaluate(
                """() => {
                    const labels = [...document.querySelectorAll('div')].filter(
                        d => d.textContent && d.textContent.trim().toLowerCase() === 'matched_rule'
                    );
                    for (const lab of labels) {
                        const parent = lab.parentElement;
                        if (!parent) continue;
                        const txt = parent.innerText.split('\\n').map(s => s.trim()).filter(Boolean);
                        const idx = txt.findIndex(t => t.toLowerCase() === 'matched_rule');
                        if (idx >= 0 && idx + 1 < txt.length) return txt[idx + 1];
                    }
                    return null;
                }"""
            )
        except Exception:
            decision_val, matched_rule = None, None
        if decision_val:
            break
        time.sleep(0.1)
    return {
        "ok": bool(decision_val),
        "decision": decision_val,
        "matched_rule": matched_rule,
        "tool": tool,
        "action": action,
        "args": args_json,
    }


# ---------------------------------------------------------------------------
# Memory search
# ---------------------------------------------------------------------------

def search_memory(
    page,
    *,
    query: str,
    semantic: bool,
    frontend_url: str,
    timeout_ms: int = 10_000,
) -> dict:
    A.nav(page, frontend_url, "/memory", timeout_ms=timeout_ms)
    A.wait(page, S.MEMORY_SEARCH_INPUT, timeout_ms=timeout_ms, state="visible")
    A.fill(page, S.MEMORY_SEARCH_INPUT, query, timeout_ms=timeout_ms)
    if semantic:
        A.click(page, S.MEMORY_SEMANTIC_BUTTON, timeout_ms=timeout_ms)
        # Wait for "Semantic results (" header to appear.
        try:
            A.wait(page, 'text=/Semantic results \\(/', timeout_ms=timeout_ms, state="visible")
        except A.UIActionError:
            pass
    else:
        # FTS debounces ~300ms. Give it a beat.
        time.sleep(0.5)

    # Scrape the visible "Memory items" or "Semantic results" table for kind/title/body.
    rows = page.evaluate(
        """() => {
            const tables = [...document.querySelectorAll('table')];
            const out = [];
            for (const t of tables) {
                const headers = [...t.querySelectorAll('thead th')].map(th => th.innerText.trim());
                const trs = [...t.querySelectorAll('tbody tr')];
                for (const tr of trs) {
                    const cells = [...tr.querySelectorAll('td')].map(td => td.innerText.trim());
                    const row = {};
                    headers.forEach((h, i) => { row[h] = cells[i]; });
                    out.push(row);
                }
            }
            return out;
        }"""
    )
    return {"ok": True, "query": query, "semantic": semantic, "results": rows}


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def list_routes() -> list[str]:
    return list(S.ROUTES)


def ping_backend(api_url: str) -> bool:
    try:
        with urllib.request.urlopen(api_url.rstrip("/") + "/approvals", timeout=2.0) as r:
            return r.status == 200
    except Exception:
        return False
