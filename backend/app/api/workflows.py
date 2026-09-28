from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["workflows"])


@router.get("/workflows")
async def list_workflows():
    root = Path(settings.AGENT_OS_ROOT) / "workflows"
    out = []
    if not root.exists():
        return out
    for f in sorted(root.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        fm = _frontmatter(content)
        out.append({"name": f.stem, "path": str(f), **fm})
    return out


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except Exception:
        return {}
