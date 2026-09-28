"""Path-safety guarantees relied on by phase 2 adapters.

Imports phase 1's `path_guard` and `paths` modules and verifies:
  * protected paths are denied
  * canonical resolution rejects ``..`` escapes
  * symlink escapes are caught
  * file-policy `protected` patterns match through `evaluate_file_write`
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from agentos_cli.core.paths import PathTraversalError, canonical
from agentos_cli.core.policy import (
    PolicyError,
    evaluate_file_write,
    load_policies,
)
from agentos_cli.safety.path_guard import (
    DEFAULT_PROTECTED,
    ProtectedPathError,
    assert_writable,
)


def test_canonical_inside_root(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    p = canonical("a/b.txt", tmp_path)
    assert str(p).startswith(str(tmp_path.resolve()))


def test_canonical_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        canonical("../../etc/passwd", tmp_path)


def test_canonical_rejects_absolute_outside_root(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        canonical("/etc/passwd", tmp_path)


def test_canonical_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir(exist_ok=True)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    link = workspace / "escape"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported on this platform")
    with pytest.raises(PathTraversalError):
        canonical("escape/leak.txt", workspace)


def test_assert_writable_blocks_protected(tmp_path: Path) -> None:
    target = tmp_path / "secret.pem"
    target.touch()
    with pytest.raises(ProtectedPathError):
        assert_writable(target, tmp_path, DEFAULT_PROTECTED)


def test_assert_writable_allows_normal_file(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    p = assert_writable(target, tmp_path, DEFAULT_PROTECTED)
    assert p == target.resolve()


def test_file_policy_denies_env(tmp_path: Path, tmp_agent_os: Path) -> None:
    policies = load_policies(tmp_agent_os / "policies")
    decision, reason = evaluate_file_write(tmp_path / ".env", tmp_path, policies)
    assert decision == "deny", reason


def test_file_policy_denies_pem(tmp_path: Path, tmp_agent_os: Path) -> None:
    policies = load_policies(tmp_agent_os / "policies")
    decision, _ = evaluate_file_write(tmp_path / "id.pem", tmp_path, policies)
    assert decision == "deny"


def test_file_policy_denies_private_dir(tmp_path: Path, tmp_agent_os: Path) -> None:
    policies = load_policies(tmp_agent_os / "policies")
    target = tmp_path / "agent-os" / "private" / "foo.md"
    decision, reason = evaluate_file_write(target, tmp_path, policies)
    assert decision == "deny", reason


def test_file_policy_allows_normal_md(tmp_path: Path, tmp_agent_os: Path) -> None:
    policies = load_policies(tmp_agent_os / "policies")
    decision, _ = evaluate_file_write(tmp_path / "docs" / "readme.md", tmp_path, policies)
    assert decision == "allow"
