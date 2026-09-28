"""Tool-neutral policy evaluation.

Pattern semantics (per builder-contract §4):
- A pattern is a list of argv tokens.
- ``"*"`` matches exactly one token (any value).
- A trailing ``"*"`` matches zero-or-more remaining tokens.
- Other tokens match literally.

Precedence: forbid > prompt > allow > default.
"""

from __future__ import annotations

import fnmatch
from typing import Any


def _match(pattern: list[str], args: list[str]) -> bool:
    if not pattern:
        return not args
    if pattern[-1] == "*":
        head = pattern[:-1]
        if len(args) < len(head):
            return False
        for p, a in zip(head, args):
            if p != "*" and p != a:
                return False
        return True
    if len(args) != len(pattern):
        return False
    for p, a in zip(pattern, args):
        if p != "*" and p != a:
            return False
    return True


def _scan(rules: list[dict[str, Any]] | None, args: list[str]) -> dict[str, Any] | None:
    if not rules:
        return None
    for rule in rules:
        pat = rule.get("pattern", [])
        if isinstance(pat, list) and _match(pat, args):
            return rule
    return None


def evaluate_shell(args: list[str], policy: dict[str, Any]) -> dict[str, Any]:
    shell = (policy or {}).get("shell", {}) or {}
    default = shell.get("default", "prompt")
    for kind in ("forbidden", "prompt", "allow"):
        match = _scan(shell.get(kind), args)
        if match:
            decision = {"forbidden": "deny", "prompt": "prompt", "allow": "allow"}[kind]
            return {"decision": decision, "matched_rule": match}
    return {"decision": default, "matched_rule": None}


def evaluate_file(path: str, policy: dict[str, Any]) -> dict[str, Any]:
    files = (policy or {}).get("files", {}) or {}
    protected: list[str] = files.get("protected", []) or []
    for pat in protected:
        # support ~ expansion and fnmatch globs
        from os.path import expanduser

        expanded = expanduser(pat)
        if fnmatch.fnmatch(path, expanded) or fnmatch.fnmatch(path, pat):
            return {"decision": "deny", "matched_rule": {"protected": pat}}
    return {"decision": "allow", "matched_rule": None}


def evaluate_mcp(server: str, op: str, policy: dict[str, Any]) -> dict[str, Any]:
    mcp = (policy or {}).get("mcp", {}) or {}
    default = mcp.get("default", "deny-write")
    if op == "read":
        if server in (mcp.get("allow_read", []) or []):
            return {"decision": "allow", "matched_rule": {"allow_read": server}}
    if op == "write":
        if server in (mcp.get("allow_write", []) or []):
            return {"decision": "allow", "matched_rule": {"allow_write": server}}
    if default == "deny-write" and op == "write":
        return {"decision": "deny", "matched_rule": {"default": default}}
    return {"decision": "allow" if default == "allow" else "deny", "matched_rule": None}


def evaluate_approval(action: str, policy: dict[str, Any]) -> dict[str, Any]:
    approval = (policy or {}).get("approval", {}) or {}
    decision = "approve"
    rule = None
    if action == "destructive" and approval.get("destructive_requires_reason"):
        decision = "prompt"
        rule = {"destructive_requires_reason": True}
    if action == "external_publication" and approval.get(
        "external_publication_requires_confirmation"
    ):
        decision = "prompt"
        rule = {"external_publication_requires_confirmation": True}
    return {"decision": decision, "matched_rule": rule}
