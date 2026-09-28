#!/usr/bin/env bash
# T-CLI-001 — agentos --help mentions all required subcommands.
set -uo pipefail
source "$(dirname "$0")/_common.sh"

OUT="$("$VENV_AGENTOS" --help 2>&1 || true)"
MISSING=()
for sub in sync validate auth-status install-adapter compile-adapters; do
  if ! grep -qE "^[[:space:]]*${sub}([[:space:]]|$)" <<<"$OUT"; then
    MISSING+=("$sub")
  fi
done

if [[ ${#MISSING[@]} -eq 0 ]]; then
  emit_result "T-CLI-001" "PASS" "all 5 subcommands present"
else
  emit_result "T-CLI-001" "FAIL" "missing subcommands: ${MISSING[*]}"
fi
