#!/usr/bin/env bash
# T-UT-001 — phase1 + phase2 + integration suites pass.
set -uo pipefail
source "$(dirname "$0")/_common.sh"

cd "$REPO_ROOT"
LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

env -u PYTHONPATH "$REPO_ROOT/.venv/bin/pytest" tests/phase1 tests/phase2 tests/integration -q >"$LOG" 2>&1
RC=$?
SUMMARY="$(tail -n 3 "$LOG" | tr '\n' ' ' | sed 's/  */ /g')"
if [[ $RC -eq 0 ]]; then
  emit_result "T-UT-001" "PASS" "pytest unit suites green — $SUMMARY"
else
  emit_result "T-UT-001" "FAIL" "pytest unit suites failed (rc=$RC) — $SUMMARY"
fi
