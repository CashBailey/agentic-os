"""Golden-path smoke runner.

Visits every route in both themes, captures a screenshot per (route, theme),
writes a JSON report. Caller passes an attached page (so the runner reuses
the daemon if one is up).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import actions as A
from . import selectors as S
from . import shortcuts as SC
from .session import STATE_DIR


def run_smoke(page, *, frontend_url: str, api_url: str) -> dict:
    started = datetime.now(timezone.utc)
    ts = started.strftime("%Y%m%dT%H%M%SZ")
    report_dir = STATE_DIR / "smoke" / ts
    report_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    overall_ok = True

    # Make sure we start in a known theme (dark) using the UI toggle.
    try:
        SC.set_theme(page, "dark")
    except Exception:
        pass

    for theme in ("dark", "light"):
        # Switch theme (toggle target) before iterating routes.
        try:
            SC.set_theme(page, theme)
        except Exception as e:
            results.append({"route": None, "theme": theme, "ok": False, "error": f"theme set failed: {e}"})
            overall_ok = False
            continue

        for route in S.ROUTES:
            entry: dict = {"route": route, "theme": theme}
            t0 = time.monotonic()
            try:
                final_url = A.nav(page, frontend_url, route, timeout_ms=15_000)
                entry["url"] = final_url
                # Briefly wait for the page header to appear so the screenshot
                # doesn't catch a blank shell.
                try:
                    A.wait(page, "h1, header", timeout_ms=3_000, state="visible")
                except A.UIActionError:
                    pass
                # Give SPA queries a beat to render skeletons.
                time.sleep(0.3)
                shot = A.screenshot(
                    page,
                    out=report_dir / f"{theme}_{_slug(route)}.png",
                    full_page=False,
                    route_for_naming=route,
                    theme_for_naming=theme,
                )
                entry["screenshot"] = str(shot)
                entry["ok"] = True
            except Exception as e:
                entry["ok"] = False
                entry["error"] = str(e)
                overall_ok = False
            entry["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            results.append(entry)

    finished = datetime.now(timezone.utc)
    report = {
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "frontend_url": frontend_url,
        "api_url": api_url,
        "routes_checked": len(S.ROUTES),
        "themes_checked": 2,
        "screenshots_taken": sum(1 for r in results if r.get("screenshot")),
        "ok": overall_ok,
        "report_dir": str(report_dir),
        "results": results,
    }
    report_path = STATE_DIR / f"smoke-{ts}.json"
    report_path.write_text(json.dumps(report, indent=2))
    report["report_path"] = str(report_path)
    return report


def _slug(route: str) -> str:
    s = route.strip("/").replace("/", "_") or "root"
    return s
