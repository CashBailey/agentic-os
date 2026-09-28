"""Canonical path resolver. Used by all builders.

`canonical(path, root)` resolves symlinks and verifies that the resulting path
is contained within `root` (also resolved). Raises `PathTraversalError` if the
resolved path escapes the root, or if `..` traversal occurs after resolution.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Union


class PathTraversalError(ValueError):
    """Raised when a path resolves outside its declared workspace root."""


PathLike = Union[str, os.PathLike]


def _resolve(p: PathLike) -> Path:
    return Path(p).expanduser().resolve(strict=False)


def canonical(path: PathLike, root: PathLike) -> Path:
    """Resolve `path` against `root` and confirm containment.

    - Tilde expansion is performed.
    - Symlinks are followed (Path.resolve).
    - If the resulting path is not equal to, or a descendant of, the resolved
      root, raises PathTraversalError.

    The check is by resolved-path prefix, so symlink escapes are caught.
    """
    root_r = _resolve(root)
    # If `path` is relative, anchor it to root before resolution so callers can
    # pass strings like "agent-os/context".
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = root_r / p
    p_r = p.resolve(strict=False)

    try:
        p_r.relative_to(root_r)
    except ValueError as e:
        raise PathTraversalError(
            f"Path {p_r!s} escapes workspace root {root_r!s}"
        ) from e
    return p_r
