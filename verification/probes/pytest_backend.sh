#!/usr/bin/env bash
# T-UT-002 — backend test suite passes.
set -uo pipefail
source "$(dirname "$0")/_common.sh"

LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

cd "$REPO_ROOT/backend"
# Backend pytest needs the backend venv (sqlalchemy, fastapi, etc.).
BACKEND_PYTEST="$REPO_ROOT/backend/.venv/bin/pytest"
[[ -x "$BACKEND_PYTEST" ]] || BACKEND_PYTEST="$REPO_ROOT/.venv/bin/pytest"
env -u PYTHONPATH "$BACKEND_PYTEST" "$REPO_ROOT/tests/backend" -q >"$LOG" 2>&1
RC=$?
SUMMARY="$(tail -n 3 "$LOG" | tr '\n' ' ' | sed 's/  */ /g')"
if [[ $RC -eq 0 ]]; then
  emit_result "T-UT-002" "PASS" "pytest backend green — $SUMMARY"
else
  emit_result "T-UT-002" "FAIL" "pytest backend failed (rc=$RC) — $SUMMARY"
fi
