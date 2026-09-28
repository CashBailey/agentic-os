"""Tests for `agentos install-adapter` — path safety, backup, dry-run."""
from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from agentos_cli.cli import main
from agentos_cli.core.paths import PathTraversalError, canonical
from agentos_cli.safety.path_guard import (
    DEFAULT_PROTECTED,
    ProtectedPathError,
    assert_writable,
)


def _run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_install_adapter_dry_run(tmp_path: Path, agent_os_root: Path) -> None:
    target = tmp_path / "repo"
    target.mkdir()
    rc, out = _run([
        "install-adapter",
        "--agent-os-root", str(agent_os_root),
        "--target", str(target),
        "--cli", "all",
        "--mode", "dry-run",
        "--json",
    ])
    assert rc == 0
    payload = json.loads(out)
    assert payload["mode"] == "dry-run"
    targets = {f["target"] for f in payload["files"]}
    # Top-level MD entries must be present.
    assert str(target / "CLAUDE.md") in targets
    assert str(target / "GEMINI.md") in targets
    assert str(target / "AGENTS.md") in targets
    # Every entry must be a would-write or skipped-no-source action (dry-run never mutates).
    actions = {f["action"] for f in payload["files"]}
    assert actions.issubset({"would-write", "skipped-no-source"}), actions
    # Nothing written
    assert not any((target / f).exists() for f in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"))
    assert not (target / ".claude").exists()
    assert not (target / ".gemini").exists()
    assert not (target / ".codex").exists()


def test_install_adapter_copy_and_backup(tmp_path: Path, agent_os_root: Path) -> None:
    target = tmp_path / "repo"
    target.mkdir()
    (target / "CLAUDE.md").write_text("PREV", encoding="utf-8")
    rc, _ = _run([
        "install-adapter",
        "--agent-os-root", str(agent_os_root),
        "--target", str(target),
        "--cli", "claude",
        "--mode", "copy",
        "--backup",
    ])
    assert rc == 0
    assert (target / "CLAUDE.md").is_file()
    backups = list(target.glob("CLAUDE.md.bak.*"))
    assert backups, "expected backup file"
    assert backups[0].read_text(encoding="utf-8") == "PREV"


def test_install_adapter_installs_per_cli_subtree(tmp_path: Path, agent_os_root: Path) -> None:
    """install-adapter must install both top-level MD AND per-CLI subtree."""
    target = tmp_path / "repo"
    target.mkdir()
    rc, out = _run([
        "install-adapter",
        "--agent-os-root", str(agent_os_root),
        "--target", str(target),
        "--cli", "all",
        "--mode", "copy",
        "--backup",
        "--json",
    ])
    assert rc == 0, out
    payload = json.loads(out)
    # Top-level MDs present
    for fname in ("CLAUDE.md", "GEMINI.md", "AGENTS.md"):
        assert (target / fname).is_file(), f"missing top-level {fname}"
    # Per-CLI subtrees present (only if compile-adapters has populated source).
    # Each subtree directory must exist with at least one file written.
    targets = {f["target"] for f in payload["files"] if f["action"] == "wrote"}
    subtree_targets = [
        t for t in targets
        if "/.claude/" in t or "/.gemini/" in t or "/.codex/" in t
    ]
    assert subtree_targets, "expected per-CLI subtree files to be installed"


def test_install_adapter_backs_up_subtree_files(tmp_path: Path, agent_os_root: Path) -> None:
    """Backup behavior must extend to subtree files, not only top-level MD."""
    target = tmp_path / "repo"
    target.mkdir()
    # Pre-create a subtree file that the installer will overwrite.
    pre_existing = target / ".claude" / "hooks" / "pre_tool_use.py"
    pre_existing.parent.mkdir(parents=True, exist_ok=True)
    pre_existing.write_text("OLD", encoding="utf-8")

    rc, out = _run([
        "install-adapter",
        "--agent-os-root", str(agent_os_root),
        "--target", str(target),
        "--cli", "claude",
        "--mode", "copy",
        "--backup",
        "--json",
    ])
    assert rc == 0, out
    backups = list(pre_existing.parent.glob("pre_tool_use.py.bak.*"))
    assert backups, "expected .bak.* sibling for subtree file"
    assert backups[0].read_text(encoding="utf-8") == "OLD"


def test_path_guard_rejects_dot_dot_traversal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    bad = root / "sub" / ".." / ".." / "etc" / "passwd"
    with pytest.raises(PathTraversalError):
        canonical(bad, root)


def test_path_guard_rejects_writes_outside_target(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "elsewhere" / "file"
    with pytest.raises(PathTraversalError):
        assert_writable(outside, root, DEFAULT_PROTECTED)


def test_path_guard_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    os.symlink(outside, link)
    target = link / "file"
    with pytest.raises(PathTraversalError):
        assert_writable(target, root, DEFAULT_PROTECTED)


def test_path_guard_rejects_env_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ProtectedPathError):
        assert_writable(root / ".env", root, DEFAULT_PROTECTED)


def test_path_guard_rejects_pem(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ProtectedPathError):
        assert_writable(root / "secret.pem", root, DEFAULT_PROTECTED)


def test_path_guard_rejects_private_dir(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "agent-os" / "private").mkdir(parents=True)
    with pytest.raises(ProtectedPathError):
        assert_writable(root / "agent-os" / "private" / "secret.md", root, DEFAULT_PROTECTED)
