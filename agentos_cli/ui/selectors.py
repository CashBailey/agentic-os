"""Central registry of Playwright selectors for the Agentic OS frontend.

Selectors here are derived from on-disk reads of:
- frontend/src/components/TopBar.tsx
- frontend/src/components/Sidebar.tsx
- frontend/src/state/theme.tsx
- frontend/src/routes/{Approvals,Adapters,Policies,Memory}.tsx

If the frontend renames a class or label, update only this file.
"""

from __future__ import annotations

# Known SPA routes (kept in sync with frontend/src/App.tsx).
ROUTES: list[str] = [
    "/",
    "/context",
    "/memory",
    "/adapters",
    "/policies",
    "/skills",
    "/approvals",
    "/audit",
]

# --- Top bar --------------------------------------------------------------

# The project dropdown is the <select aria-label="Project"> in TopBar.tsx.
PROJECT_SELECT = 'select[aria-label="Project"]'

# The theme toggle is the only button in the top header with aria-label
# matching "Switch to ... theme". We use a starts-with match so it works in
# either state.
THEME_TOGGLE = 'button[aria-label^="Switch to "]'

# --- Approvals -----------------------------------------------------------

def approve_button(approval_id: int) -> str:
    """Locator for the Approve button in the row whose id cell reads '#<id>'."""
    return f'role=row >> text="#{approval_id}" >> .. >> role=button[name="Approve"]'


def deny_button(approval_id: int) -> str:
    return f'role=row >> text="#{approval_id}" >> .. >> role=button[name="Deny"]'


# Simpler fallback locators using Playwright's `:has()` engine.
def approve_button_css(approval_id: int) -> str:
    return f'tr:has(td:has-text("#{approval_id}")) button:has-text("Approve")'


def deny_button_css(approval_id: int) -> str:
    return f'tr:has(td:has-text("#{approval_id}")) button:has-text("Deny")'


def approval_row(approval_id: int) -> str:
    return f'tr:has(td:has-text("#{approval_id}"))'


# --- Adapters ------------------------------------------------------------

# The "Compile now" button text changes to "Enqueuing…" while pending.
COMPILE_ADAPTERS_BUTTON = 'button:has-text("Compile now"), button:has-text("Enqueuing")'

# --- Policies simulator --------------------------------------------------

# Inputs in the simulator card. We can't rely on placeholder text (none),
# so we locate by label-text proximity using Playwright's text engine.
# The simulator card has three Inputs and a Simulate button.
POLICY_SIMULATE_BUTTON = 'button:has-text("Simulate"):not(:has-text("Simulating"))'

# Inputs come in DOM order: tool, action, args. We expose them as a tuple
# locator for the shortcut.
POLICY_SIM_INPUTS_CONTAINER = 'div:has(> div > label:has-text("tool"))'

# --- Memory --------------------------------------------------------------

MEMORY_SEARCH_INPUT = 'input[placeholder^="Search (FTS)"]'
MEMORY_SEMANTIC_BUTTON = 'button:has-text("Semantic search")'

# --- Health --------------------------------------------------------------

# The app shell renders a header on every route. We use it to confirm the
# SPA has hydrated.
APP_SHELL_HEADER = "header"
