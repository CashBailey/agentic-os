"""Conftest for tests/unit/ — adds backend/ to sys.path so `app.*` imports work."""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
_BACKEND = _REPO / "backend"
for p in (_BACKEND, _REPO):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
