"""CLI-driven control plane for the Agentic OS frontend.

Modules:
- selectors: centralized Playwright locator strings (one file to update when
  the frontend changes).
- session: persistent browser daemon lifecycle (start/stop/status) and
  context managers for one-shot or attach-to-daemon execution.
- actions: low-level page primitives (nav/click/fill/eval/screenshot/...).
- shortcuts: high-level UI shortcuts that wrap actions for common flows
  (theme toggle, project switch, approve/deny, compile-adapters, etc.).
- smoke: golden-path runner that exercises every route in both themes.
"""

from __future__ import annotations

__all__ = [
    "selectors",
    "session",
    "actions",
    "shortcuts",
    "smoke",
]
