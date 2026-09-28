"""Path-write safety guard. phase2 imports `assert_writable` from here."""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable, Union

from agentos_cli.core.paths import canonical, PathTraversalError

PathLike = Union[str, os.PathLike]


# Default protected globs — match contract §4 file-policy.yaml `files.protected`.
DEFAULT_PROTECTED: tuple[str, ...] = (
    ".env",
    "*.pem",
    "*.key",
    "agent-os/private/**",
    "~/.codex/auth.json",
    "~/.claude/.credentials.json",
    "~/.config/gemini/**",
)


class ProtectedPathError(PermissionError):
    """Raised when a write target matches a protected pattern."""


def _normalize_pattern(pat: str) -> str:
    return str(Path(pat).expanduser())


def _matches(target_abs: Path, pattern: str, workspace_root: Path) -> bool:
    """Return True if `target_abs` matches `pattern`.

    Pattern semantics:
      - Patterns starting with `~` or `/` are absolute (expanded).
      - Other patterns are evaluated:
          (a) as a basename glob against `target_abs.name`
          (b) as a workspace-relative glob against the path relative to root
      - `**` matches multiple path components.
    """
    expanded = _normalize_pattern(pattern)

    # Absolute pattern (after expansion): match against full target path.
    if expanded.startswith(("/", os.sep)):
        # Use fnmatchcase on string form. fnmatch handles `*` but not `**`
        # uniformly; convert `**` to `*` for matching, since fnmatch's `*`
        # already matches path separators.
        return fnmatch.fnmatchcase(str(target_abs), expanded.replace("**", "*"))

    # Relative pattern: try basename, then workspace-relative.
    if fnmatch.fnmatchcase(target_abs.name, expanded):
        return True
    try:
        rel = target_abs.relative_to(workspace_root)
    except ValueError:
        return False
    rel_str = str(rel)
    return fnmatch.fnmatchcase(rel_str, expanded.replace("**", "*"))


def assert_writable(
    target: PathLike,
    workspace_root: PathLike,
    protected: Iterable[str] = DEFAULT_PROTECTED,
) -> Path:
    """Raise if `target` is outside `workspace_root` or matches a protected glob.

    Returns the canonical resolved target path on success.
    """
    root_r = Path(workspace_root).expanduser().resolve(strict=False)
    try:
        target_r = canonical(target, root_r)
    except PathTraversalError:
        # Re-raise as a ProtectedPathError so callers can treat all
        # write-rejection reasons uniformly. Keep PathTraversalError visible
        # for callers that want to distinguish — but here we re-raise the
        # original to preserve type identity. Choose: bubble PathTraversalError.
        raise

    for pat in protected:
        if _matches(target_r, pat, root_r):
            raise ProtectedPathError(
                f"Refusing to write protected path: {target_r} (pattern: {pat})"
            )

    # Additionally: protected absolute paths regardless of workspace.
    # e.g. ~/.claude/.credentials.json — these should match even if root differs.
    for pat in protected:
        expanded = _normalize_pattern(pat)
        if expanded.startswith(("/", os.sep)):
            if fnmatch.fnmatchcase(
                str(target_r), expanded.replace("**", "*")
            ):
                raise ProtectedPathError(
                    f"Refusing to write protected path: {target_r} (pattern: {pat})"
                )

    return target_r
