"""Loads canonical global + project context and concatenates it for adapter output."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agentos_cli.core.templates import parse_file, ParsedDocument


@dataclass
class LoadedContext:
    global_docs: list[ParsedDocument] = field(default_factory=list)
    project_docs: list[ParsedDocument] = field(default_factory=list)
    workflow_docs: list[ParsedDocument] = field(default_factory=list)
    skill_docs: list[ParsedDocument] = field(default_factory=list)
    project_slug: Optional[str] = None


def _safe_load(p: Path) -> Optional[ParsedDocument]:
    if not p.exists() or not p.is_file():
        return None
    try:
        return parse_file(p)
    except Exception:
        return None


def load_context(agent_os_root: Path, project_slug: Optional[str] = None) -> LoadedContext:
    """Read the canonical files under `agent_os_root` for the given project."""
    lc = LoadedContext(project_slug=project_slug)

    # global context
    g_ctx = agent_os_root / "context" / "global"
    if g_ctx.is_dir():
        for p in sorted(g_ctx.glob("*.md")):
            doc = _safe_load(p)
            if doc:
                lc.global_docs.append(doc)

    # global memory (treat as context for adapter concat)
    g_mem = agent_os_root / "memory" / "global"
    if g_mem.is_dir():
        for p in sorted(g_mem.glob("*.md")):
            doc = _safe_load(p)
            if doc:
                lc.global_docs.append(doc)

    # workflows
    wf = agent_os_root / "workflows"
    if wf.is_dir():
        for p in sorted(wf.glob("*.md")):
            doc = _safe_load(p)
            if doc:
                lc.workflow_docs.append(doc)

    # skills (each SKILL.md)
    sk = agent_os_root / "skills"
    if sk.is_dir():
        for skill_md in sorted(sk.rglob("SKILL.md")):
            doc = _safe_load(skill_md)
            if doc:
                lc.skill_docs.append(doc)

    # project-scoped context + memory
    if project_slug:
        p_ctx = agent_os_root / "context" / "projects" / project_slug
        if p_ctx.is_dir():
            for p in sorted(p_ctx.glob("*.md")):
                # skip private *.local.md files from adapter output
                if p.name.endswith(".local.md"):
                    continue
                doc = _safe_load(p)
                if doc:
                    lc.project_docs.append(doc)
        p_mem = agent_os_root / "memory" / "projects" / project_slug
        if p_mem.is_dir():
            for p in sorted(p_mem.glob("*.md")):
                if p.name.endswith(".local.md"):
                    continue
                doc = _safe_load(p)
                if doc:
                    lc.project_docs.append(doc)

    return lc


def render_unified_markdown(lc: LoadedContext) -> str:
    """Produce one markdown document combining global + project context.

    Output structure is deterministic so adapters (CLAUDE.md, GEMINI.md, AGENTS.md)
    are byte-identical.
    """
    parts: list[str] = []
    parts.append("# Agentic OS — Unified Context\n")
    if lc.project_slug:
        parts.append(f"\n_Project: `{lc.project_slug}`_\n")
    parts.append("\n")

    def _section(title: str, docs: list[ParsedDocument]) -> None:
        if not docs:
            return
        parts.append(f"\n## {title}\n\n")
        for d in docs:
            parts.append(f"### {d.path.name}\n\n")
            body = d.body.strip()
            if body:
                parts.append(body)
                parts.append("\n\n")

    _section("Global Context", lc.global_docs)
    _section("Project Context", lc.project_docs)
    _section("Workflows", lc.workflow_docs)
    _section("Skills", lc.skill_docs)

    return "".join(parts)
