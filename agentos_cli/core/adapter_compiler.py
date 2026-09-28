"""Adapter compiler orchestrator.

Loads policies + adapter configs + canonical context, calls each adapter
emitter, and writes outputs to ``agent-os/generated/{cli}/**`` deterministically.

Determinism guarantees:
  * Emitted file lists are sorted by path before write.
  * JSON outputs use ``sort_keys=True`` + ``indent=2`` + trailing newline.
  * No timestamps in any emitted file (intentional — re-runs must be
    byte-identical).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from agentos_cli.core import claude_adapter, codex_adapter, gemini_adapter
from agentos_cli.core.context_loader import load_context, render_unified_markdown
from agentos_cli.core.policy import Policies, PolicyError, load_policies


class AdapterSpecError(ValueError):
    """Raised when an adapter YAML config fails to load or validate."""


_ADAPTERS = (
    ("claude", claude_adapter),
    ("gemini", gemini_adapter),
    ("codex", codex_adapter),
)


@dataclass
class CompileResult:
    cli: str
    files: list[dict] = field(default_factory=list)  # [{path, bytes, sha256}]
    written: bool = False


@dataclass
class CompileReport:
    policies_dir: Path
    adapters_dir: Path
    generated_root: Path
    project_slug: Optional[str]
    results: list[CompileResult] = field(default_factory=list)
    source_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "policies_dir": str(self.policies_dir),
            "adapters_dir": str(self.adapters_dir),
            "generated_root": str(self.generated_root),
            "project_slug": self.project_slug,
            "source_hash": self.source_hash,
            "results": [
                {
                    "cli": r.cli,
                    "written": r.written,
                    "files": r.files,
                }
                for r in self.results
            ],
        }


def _load_adapter_yaml(p: Path) -> dict:
    if not p.is_file():
        raise AdapterSpecError(f"adapter spec missing: {p}")
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as e:
        raise AdapterSpecError(f"YAML parse error in {p}: {e}") from e
    if not isinstance(data, dict):
        raise AdapterSpecError(f"{p}: top-level must be a mapping")
    # Minimal required keys
    required = ("cli", "context_filename", "output_subdir", "hooks_subdir", "hooks")
    for k in required:
        if k not in data:
            raise AdapterSpecError(f"{p}: missing required key {k!r}")
    if not isinstance(data["hooks"], list):
        raise AdapterSpecError(f"{p}: 'hooks' must be a list")
    return data


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _source_hash(policies: Policies, adapter_cfgs: dict[str, dict], context_md: str) -> str:
    h = hashlib.sha256()
    # Include the raw policy source bytes for stability.
    for key in sorted(policies.source_paths):
        p = policies.source_paths[key]
        h.update(key.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    for cli in sorted(adapter_cfgs):
        h.update(cli.encode("utf-8"))
        h.update(b"\0")
        h.update(json.dumps(adapter_cfgs[cli], sort_keys=True).encode("utf-8"))
        h.update(b"\0")
    h.update(b"context")
    h.update(b"\0")
    h.update(context_md.encode("utf-8"))
    return h.hexdigest()


def compile_all(
    agent_os_root: Path,
    project_slug: Optional[str] = None,
    check_only: bool = False,
) -> CompileReport:
    """Run the full compile.

    Args:
        agent_os_root: path to ``agent-os/`` directory containing policies/,
            adapters/, context/, etc.
        project_slug: optional project slug to include project-scoped context.
        check_only: if True, validate + render to memory but do not write.

    Raises:
        PolicyError: on policy load/validate failure (exit 1).
        AdapterSpecError: on adapter spec failure (exit 2).
    """
    agent_os_root = Path(agent_os_root)
    policies_dir = agent_os_root / "policies"
    adapters_dir = agent_os_root / "adapters"
    generated_root = agent_os_root / "generated"

    policies = load_policies(policies_dir)  # PolicyError on failure

    adapter_cfgs: dict[str, dict] = {}
    for cli, _mod in _ADAPTERS:
        adapter_cfgs[cli] = _load_adapter_yaml(adapters_dir / f"{cli}.yaml")

    lc = load_context(agent_os_root, project_slug=project_slug)
    context_md = render_unified_markdown(lc)

    src_hash = _source_hash(policies, adapter_cfgs, context_md)

    report = CompileReport(
        policies_dir=policies_dir,
        adapters_dir=adapters_dir,
        generated_root=generated_root,
        project_slug=project_slug,
        source_hash=src_hash,
    )

    for cli, mod in _ADAPTERS:
        cfg = adapter_cfgs[cli]
        files = mod.emit(generated_root, context_md, policies, cfg)
        # Sort by path for deterministic write order.
        files_sorted = sorted(files, key=lambda t: str(t[0]))
        cli_result = CompileResult(cli=cli)
        if not check_only:
            for path, content in files_sorted:
                path.parent.mkdir(parents=True, exist_ok=True)
                # Write only if changed (preserves mtime on no-op compiles).
                if path.exists() and path.read_bytes() == content:
                    pass
                else:
                    path.write_bytes(content)
            cli_result.written = True
        # Always populate the manifest (path/bytes/sha) for the report.
        for path, content in files_sorted:
            cli_result.files.append(
                {
                    "path": str(path),
                    "bytes": len(content),
                    "sha256": _sha256(content),
                }
            )
        report.results.append(cli_result)

    return report
