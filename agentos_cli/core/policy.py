"""Policy loading + evaluation.

Loads ``agent-os/policies/{shell,file,mcp,approval}-policy.yaml`` and exposes:

- ``load_policies(policies_dir) -> Policies``
- ``evaluate_shell(argv, policies) -> (decision, matched_rule)``
- ``evaluate_file_write(path, workspace_root, policies) -> (decision, reason)``

Pattern semantics (shell):
  * Each rule's ``pattern`` is a list of tokens matched against ``argv``.
  * Literal tokens must equal the argv token at the same position.
  * ``"*"`` matches exactly one argv token (any value).
  * A trailing ``"*"`` matches zero-or-more remaining tokens (i.e. a prefix
    match — once we reach a trailing star, the rule matches regardless of how
    many tokens remain).

Default decision (when no rule matches) is taken from
``shell.default`` in shell-policy.yaml; contract §0 locks this to ``prompt``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import fnmatch
import os
import yaml


VALID_DECISIONS = ("allow", "prompt", "forbid")


class PolicyError(ValueError):
    """Raised when a policy file fails to load or validate."""


@dataclass
class ShellPolicy:
    default: str = "prompt"
    forbidden: list[dict] = field(default_factory=list)
    prompt: list[dict] = field(default_factory=list)
    allow: list[dict] = field(default_factory=list)


@dataclass
class FilePolicy:
    protected: list[str] = field(default_factory=list)
    generated_roots: list[str] = field(default_factory=list)
    workspace_roots: list[str] = field(default_factory=list)


@dataclass
class McpPolicy:
    default: str = "deny-write"
    allow_read: list[str] = field(default_factory=list)
    allow_write: list[str] = field(default_factory=list)


@dataclass
class ApprovalPolicy:
    destructive_requires_reason: bool = True
    external_publication_requires_confirmation: bool = True
    ttl_seconds: int = 300


@dataclass
class Policies:
    shell: ShellPolicy = field(default_factory=ShellPolicy)
    files: FilePolicy = field(default_factory=FilePolicy)
    mcp: McpPolicy = field(default_factory=McpPolicy)
    approval: ApprovalPolicy = field(default_factory=ApprovalPolicy)
    source_paths: dict[str, Path] = field(default_factory=dict)


# ---------------------------------------------------------------- loaders ---

def _read_yaml(p: Path) -> dict:
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError as e:
        raise PolicyError(f"policy file missing: {p}") from e
    except yaml.YAMLError as e:
        raise PolicyError(f"YAML parse error in {p}: {e}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise PolicyError(f"{p}: top-level must be a mapping, got {type(data).__name__}")
    return data


def _validate_rule_list(items: Any, where: str) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise PolicyError(f"{where}: expected list, got {type(items).__name__}")
    out: list[dict] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise PolicyError(f"{where}[{i}]: expected mapping")
        pattern = raw.get("pattern")
        if not isinstance(pattern, list) or not all(isinstance(t, str) for t in pattern):
            raise PolicyError(f"{where}[{i}].pattern: expected list[str]")
        reason = raw.get("reason", "")
        if reason is not None and not isinstance(reason, str):
            raise PolicyError(f"{where}[{i}].reason: expected str")
        out.append({"pattern": list(pattern), "reason": reason or ""})
    return out


def load_shell_policy(p: Path) -> ShellPolicy:
    data = _read_yaml(p)
    shell = data.get("shell", {})
    if not isinstance(shell, dict):
        raise PolicyError(f"{p}: 'shell' must be a mapping")
    default = shell.get("default", "prompt")
    if default not in VALID_DECISIONS:
        raise PolicyError(
            f"{p}: shell.default must be one of {VALID_DECISIONS}, got {default!r}"
        )
    return ShellPolicy(
        default=default,
        forbidden=_validate_rule_list(shell.get("forbidden"), f"{p}:shell.forbidden"),
        prompt=_validate_rule_list(shell.get("prompt"), f"{p}:shell.prompt"),
        allow=_validate_rule_list(shell.get("allow"), f"{p}:shell.allow"),
    )


def load_file_policy(p: Path) -> FilePolicy:
    data = _read_yaml(p)
    files = data.get("files", {})
    if not isinstance(files, dict):
        raise PolicyError(f"{p}: 'files' must be a mapping")
    def _slist(key: str) -> list[str]:
        v = files.get(key, [])
        if v is None:
            return []
        if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
            raise PolicyError(f"{p}: files.{key} must be list[str]")
        return list(v)
    return FilePolicy(
        protected=_slist("protected"),
        generated_roots=_slist("generated_roots"),
        workspace_roots=_slist("workspace_roots"),
    )


def load_mcp_policy(p: Path) -> McpPolicy:
    data = _read_yaml(p)
    mcp = data.get("mcp", {})
    if not isinstance(mcp, dict):
        raise PolicyError(f"{p}: 'mcp' must be a mapping")
    default = mcp.get("default", "deny-write")
    if default not in ("allow", "deny-write", "deny"):
        raise PolicyError(f"{p}: mcp.default invalid: {default!r}")
    def _slist(key: str) -> list[str]:
        v = mcp.get(key, [])
        if v is None:
            return []
        if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
            raise PolicyError(f"{p}: mcp.{key} must be list[str]")
        return list(v)
    return McpPolicy(
        default=default,
        allow_read=_slist("allow_read"),
        allow_write=_slist("allow_write"),
    )


def load_approval_policy(p: Path) -> ApprovalPolicy:
    data = _read_yaml(p)
    ap = data.get("approval", {})
    if not isinstance(ap, dict):
        raise PolicyError(f"{p}: 'approval' must be a mapping")
    ttl = ap.get("ttl_seconds", 300)
    if not isinstance(ttl, int) or ttl <= 0:
        raise PolicyError(f"{p}: approval.ttl_seconds must be positive int")
    return ApprovalPolicy(
        destructive_requires_reason=bool(ap.get("destructive_requires_reason", True)),
        external_publication_requires_confirmation=bool(
            ap.get("external_publication_requires_confirmation", True)
        ),
        ttl_seconds=ttl,
    )


def load_policies(policies_dir: Path) -> Policies:
    """Load all four policy files from a directory.

    Missing files are treated as parse errors (fail-closed) — every deployment
    must ship the four canonical YAML files.
    """
    pd = Path(policies_dir)
    shell_p = pd / "shell-policy.yaml"
    file_p = pd / "file-policy.yaml"
    mcp_p = pd / "mcp-policy.yaml"
    appr_p = pd / "approval-policy.yaml"
    pols = Policies(
        shell=load_shell_policy(shell_p),
        files=load_file_policy(file_p),
        mcp=load_mcp_policy(mcp_p),
        approval=load_approval_policy(appr_p),
        source_paths={
            "shell": shell_p,
            "files": file_p,
            "mcp": mcp_p,
            "approval": appr_p,
        },
    )
    return pols


# ---------------------------------------------------------- evaluation -----

def _pattern_matches(pattern: list[str], argv: list[str]) -> bool:
    """Match `pattern` against `argv`.

    See module docstring for semantics: literal tokens equal, ``"*"`` matches
    one token, trailing ``"*"`` matches zero-or-more remaining tokens.
    """
    if not pattern:
        return False
    pi = 0
    ai = 0
    while pi < len(pattern):
        ptok = pattern[pi]
        # Trailing star: consume everything that's left.
        if ptok == "*" and pi == len(pattern) - 1:
            return True
        if ai >= len(argv):
            return False
        if ptok == "*":
            # match exactly one token (any value)
            ai += 1
            pi += 1
            continue
        if ptok != argv[ai]:
            return False
        ai += 1
        pi += 1
    # All pattern tokens consumed; require argv consumed too (no trailing *).
    return ai == len(argv)


def evaluate_shell(argv: list[str], policies: Policies) -> tuple[str, Optional[dict]]:
    """Evaluate argv against shell policy.

    Order: forbidden > prompt > allow > default. (Forbidden always wins, even
    if a more permissive rule also matches.)
    Returns (decision, matched_rule_dict_or_None).
    """
    if not argv:
        return "forbid", {"reason": "empty argv"}
    sp = policies.shell
    for rule in sp.forbidden:
        if _pattern_matches(rule["pattern"], argv):
            return "forbid", rule
    for rule in sp.prompt:
        if _pattern_matches(rule["pattern"], argv):
            return "prompt", rule
    for rule in sp.allow:
        if _pattern_matches(rule["pattern"], argv):
            return "allow", rule
    return sp.default, None


# --------------------------------------------------------- file policy ----

def _expand(pat: str) -> str:
    return str(Path(pat).expanduser())


def _file_matches(target_abs: Path, pattern: str, workspace_root: Path) -> bool:
    expanded = _expand(pattern)
    # Absolute pattern after expansion → match against the absolute path.
    if expanded.startswith(("/", os.sep)):
        return fnmatch.fnmatchcase(str(target_abs), expanded.replace("**", "*"))
    # Basename glob
    if fnmatch.fnmatchcase(target_abs.name, expanded):
        return True
    # Workspace-relative glob
    try:
        rel = target_abs.relative_to(workspace_root)
    except ValueError:
        return False
    return fnmatch.fnmatchcase(str(rel), expanded.replace("**", "*"))


def evaluate_file_write(
    path: Path,
    workspace_root: Path,
    policies: Policies,
) -> tuple[str, str]:
    """Return ('allow'|'deny', reason)."""
    target = Path(path).expanduser()
    # The caller is expected to have run canonical() / assert_writable for
    # traversal-rejection; this function only checks protected patterns.
    if not target.is_absolute():
        target = (Path(workspace_root) / target)
    target = target.resolve(strict=False)
    root = Path(workspace_root).expanduser().resolve(strict=False)
    for pat in policies.files.protected:
        if _file_matches(target, pat, root):
            return "deny", f"matched protected pattern: {pat}"
    return "allow", ""


# --------------------------------------------------------- mcp policy ----

def evaluate_mcp(
    server: str,
    op: str,
    policies: Policies,
) -> tuple[str, str]:
    """Return ('allow'|'deny', reason) for an MCP tool call.

    op ∈ {"read", "write"}.
    """
    mp = policies.mcp
    if op == "read":
        if server in mp.allow_read:
            return "allow", "in allow_read"
        if mp.default in ("allow",):
            return "allow", "default allow"
        return "deny", f"server {server!r} not in allow_read"
    if op == "write":
        if server in mp.allow_write:
            return "allow", "in allow_write"
        return "deny", f"server {server!r} not in allow_write"
    return "deny", f"unknown op {op!r}"


def policy_summary(policies: Policies) -> dict:
    """Compact JSON-safe summary of loaded policies (for `compile --check --json`)."""
    return {
        "shell": {
            "default": policies.shell.default,
            "forbidden_count": len(policies.shell.forbidden),
            "prompt_count": len(policies.shell.prompt),
            "allow_count": len(policies.shell.allow),
        },
        "files": {
            "protected_count": len(policies.files.protected),
            "generated_roots": policies.files.generated_roots,
        },
        "mcp": {
            "default": policies.mcp.default,
            "allow_read": policies.mcp.allow_read,
            "allow_write": policies.mcp.allow_write,
        },
        "approval": {
            "ttl_seconds": policies.approval.ttl_seconds,
            "destructive_requires_reason": policies.approval.destructive_requires_reason,
        },
    }
