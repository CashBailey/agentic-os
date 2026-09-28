"""Canonical template registry and YAML front-matter parsing."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


# (relative_path_under_agent_os, kind)
# kind: 'context-global' | 'context-project' | 'memory-global' | 'memory-project'
#       | 'skill' | 'workflow' | 'template' | 'private'
REQUIRED_GLOBAL_CONTEXT: tuple[str, ...] = (
    "context/global/user.md",
    "context/global/developer-profile.md",
    "context/global/communication-preferences.md",
    "context/global/coding-standards.md",
    "context/global/tool-preferences.md",
    "context/global/security-boundaries.md",
    "context/global/ai-behavior-rules.md",
)

REQUIRED_GLOBAL_MEMORY: tuple[str, ...] = (
    "memory/global/durable-preferences.md",
    "memory/global/cross-project-lessons.md",
)

REQUIRED_WORKFLOWS: tuple[str, ...] = (
    "workflows/session-start.md",
    "workflows/session-end.md",
    "workflows/new-feature.md",
    "workflows/bug-fix.md",
    "workflows/security-review.md",
)

REQUIRED_TEMPLATES: tuple[str, ...] = (
    "templates/adr.md",
    "templates/prd.md",
    "templates/feature-spec.md",
    "templates/bug-report.md",
    "templates/research-brief.md",
)

REQUIRED_SKILLS: tuple[str, ...] = (
    "skills/session-start/SKILL.md",
    "skills/session-end/SKILL.md",
    "skills/new-feature/SKILL.md",
    "skills/bug-fix/SKILL.md",
    "skills/security-review/SKILL.md",
)

REQUIRED_PROJECT_CONTEXT: tuple[str, ...] = (
    "project-context.md",
    "architecture.md",
    "standards.md",
    "workflows.md",
)

REQUIRED_PROJECT_MEMORY: tuple[str, ...] = (
    "project-memory.md",
    "decisions.md",
    "session-log.md",
    "open-questions.md",
)


@dataclass
class ParsedDocument:
    path: Path
    frontmatter: Optional[dict[str, Any]] = None
    body: str = ""
    parse_error: Optional[str] = None
    frontmatter_lines: tuple[int, int] = (0, 0)  # (start_line, end_line) of frontmatter block


def parse_markdown_frontmatter(text: str) -> ParsedDocument:
    """Parse `---\n...yaml...\n---\nbody` style front-matter.

    Returns a ParsedDocument with `parse_error` set if YAML fails.
    The result has `path=Path()` — callers should set it.
    """
    doc = ParsedDocument(path=Path())
    if not text.startswith("---"):
        doc.body = text
        return doc

    lines = text.splitlines(keepends=True)
    # find closing '---'
    end_idx = None
    for i in range(1, len(lines)):
        stripped = lines[i].rstrip("\n").rstrip("\r")
        if stripped == "---":
            end_idx = i
            break
    if end_idx is None:
        # malformed — no closing fence; treat as body, flag error
        doc.body = text
        doc.parse_error = "front-matter has no closing '---' fence"
        return doc

    yaml_block = "".join(lines[1:end_idx])
    try:
        fm = yaml.safe_load(yaml_block)
        if fm is not None and not isinstance(fm, dict):
            doc.parse_error = "front-matter is not a YAML mapping"
        else:
            doc.frontmatter = fm or {}
    except yaml.YAMLError as e:
        doc.parse_error = f"YAML parse error: {e}"
    doc.body = "".join(lines[end_idx + 1 :])
    doc.frontmatter_lines = (1, end_idx + 1)
    return doc


def parse_file(path: Path) -> ParsedDocument:
    text = path.read_text(encoding="utf-8")
    doc = parse_markdown_frontmatter(text)
    doc.path = path
    return doc
