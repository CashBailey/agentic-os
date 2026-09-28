#!/usr/bin/env bash
# T-POL-PROBE-001 — codex execpolicy returns allow for a safe command.
set -uo pipefail
source "$(dirname "$0")/_common.sh"

RULES="$REPO_ROOT/agent-os/generated/codex/rules/agentic-os.rules"
if [[ ! -f "$RULES" ]]; then
  emit_result "T-POL-PROBE-001" "FAIL" "rules file missing: $RULES"
fi
if ! command -v codex >/dev/null 2>&1; then
  emit_result "T-POL-PROBE-001" "FAIL" "codex CLI not on PATH"
fi

OUT="$(codex execpolicy check --rules "$RULES" git status 2>&1 || true)"
DECISION="$("$VENV_PY" -c "import json,sys
try:
    d=json.loads(sys.stdin.read())
    print(d.get('decision') or d.get('result') or d.get('outcome') or '')
except Exception:
    print('')
" <<<"$OUT" 2>/dev/null || true)"

if [[ "$DECISION" == "allow" || "$DECISION" == "allowed" ]]; then
  emit_result "T-POL-PROBE-001" "PASS" "execpolicy decision=$DECISION for 'git status'"
else
  # Fallback: if decision key differs, grep for allow token.
  if grep -qE '"(decision|result|outcome)"\s*:\s*"(allow|allowed)"' <<<"$OUT"; then
    emit_result "T-POL-PROBE-001" "PASS" "execpolicy allow (grep fallback)"
  fi
  emit_result "T-POL-PROBE-001" "FAIL" "execpolicy did not allow git status: $OUT"
fi
