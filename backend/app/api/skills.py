from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["skills"])


@router.get("/skills")
async def list_skills():
    root = Path(settings.AGENT_OS_ROOT) / "skills"
    out = []
    if not root.exists():
        return out
    for skill_dir in sorted(root.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        content = skill_md.read_text(encoding="utf-8")
        fm = _frontmatter(content)
        out.append({"name": skill_dir.name, "path": str(skill_md), **fm})
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
