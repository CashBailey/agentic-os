"""Compile policies into per-CLI outputs and verify byte-for-byte determinism."""
from __future__ import annotations

import hashlib
from pathlib import Path

from agentos_cli.core.adapter_compiler import compile_all


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def test_compile_writes_all_three_clis(tmp_agent_os: Path) -> None:
    report = compile_all(tmp_agent_os)
    clis = sorted(r.cli for r in report.results)
    assert clis == ["claude", "codex", "gemini"]
    gen = tmp_agent_os / "generated"
    assert (gen / "CLAUDE.md").is_file()
    assert (gen / "GEMINI.md").is_file()
    assert (gen / "AGENTS.md").is_file()
    assert (gen / "claude" / "settings.json").is_file()
    assert (gen / "claude" / "hooks" / "pre_tool_use.py").is_file()
    assert (gen / "claude" / "hooks" / "pre_file_write.py").is_file()
    assert (gen / "claude" / "hooks" / "session_start.py").is_file()
    assert (gen / "gemini" / "settings.json").is_file()
    assert (gen / "gemini" / "hooks" / "before_tool.py").is_file()
    assert (gen / "codex" / "config.toml").is_file()
    assert (gen / "codex" / "hooks" / "tool_before.py").is_file()
    assert (gen / "codex" / "rules" / "agentic-os.rules").is_file()


def test_compile_is_deterministic(tmp_agent_os: Path) -> None:
    compile_all(tmp_agent_os)
    h1 = _tree_hash(tmp_agent_os / "generated")
    compile_all(tmp_agent_os)
    h2 = _tree_hash(tmp_agent_os / "generated")
    assert h1 == h2, "compile-adapters must produce byte-identical outputs across runs"


def test_compile_check_does_not_write(tmp_agent_os: Path) -> None:
    gen = tmp_agent_os / "generated"
    before = sorted(p for p in gen.rglob("*") if p.is_file())
    report = compile_all(tmp_agent_os, check_only=True)
    after = sorted(p for p in gen.rglob("*") if p.is_file())
    assert before == after, "check-only must not write files"
    # report should still enumerate files
    total = sum(len(r.files) for r in report.results)
    assert total > 0


def test_settings_json_is_sorted_and_pretty(tmp_agent_os: Path) -> None:
    import json
    compile_all(tmp_agent_os)
    s = (tmp_agent_os / "generated" / "claude" / "settings.json").read_text("utf-8")
    # Round-trip parses
    data = json.loads(s)
    # Sorted keys + indent=2 ⇒ re-serialising yields the same string.
    again = json.dumps(data, indent=2, sort_keys=True) + "\n"
    assert s == again


def test_source_hash_changes_when_policy_changes(tmp_agent_os: Path) -> None:
    r1 = compile_all(tmp_agent_os, check_only=True)
    p = tmp_agent_os / "policies" / "shell-policy.yaml"
    p.write_text(p.read_text("utf-8") + "\n# touched\n", encoding="utf-8")
    r2 = compile_all(tmp_agent_os, check_only=True)
    assert r1.source_hash != r2.source_hash
