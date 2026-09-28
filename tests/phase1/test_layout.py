"""Verify the canonical layout, required files, and .gitignore coverage."""
from __future__ import annotations

from pathlib import Path

from agentos_cli.core.templates import (
    REQUIRED_GLOBAL_CONTEXT,
    REQUIRED_GLOBAL_MEMORY,
    REQUIRED_SKILLS,
    REQUIRED_TEMPLATES,
    REQUIRED_WORKFLOWS,
)


REQUIRED_DIRS = (
    "agent-os/context/global",
    "agent-os/context/projects",
    "agent-os/memory/global",
    "agent-os/memory/projects",
    "agent-os/skills",
    "agent-os/workflows",
    "agent-os/templates",
    "agent-os/private",
)


def test_required_dirs_exist(repo_root: Path) -> None:
    for d in REQUIRED_DIRS:
        p = repo_root / d
        assert p.is_dir(), f"missing required directory: {p}"


def test_required_files_exist(agent_os_root: Path) -> None:
    required = (
        list(REQUIRED_GLOBAL_CONTEXT)
        + list(REQUIRED_GLOBAL_MEMORY)
        + list(REQUIRED_WORKFLOWS)
        + list(REQUIRED_TEMPLATES)
        + list(REQUIRED_SKILLS)
    )
    missing = [r for r in required if not (agent_os_root / r).is_file()]
    assert not missing, f"missing required files: {missing}"


def test_gitignore_excludes_sensitive(repo_root: Path) -> None:
    gi = (repo_root / ".gitignore").read_text(encoding="utf-8")
    for pat in (".env", "*.local.md", "agent-os/private/", "agent-os/generated/", "agent-os/outputs/"):
        assert pat in gi, f".gitignore missing pattern: {pat}"
