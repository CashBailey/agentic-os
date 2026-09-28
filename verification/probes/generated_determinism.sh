#!/usr/bin/env bash
# T-ADP-PROBE-001 — compile-adapters is deterministic (sha256 stable across runs).
set -uo pipefail
source "$(dirname "$0")/_common.sh"

GEN="$REPO_ROOT/agent-os/generated"
hash_tree() {
  ( cd "$GEN" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}' )
}

"$VENV_AGENTOS" compile-adapters --json >/dev/null 2>&1 || \
  emit_result "T-ADP-PROBE-001" "FAIL" "first compile-adapters run failed"
H1="$(hash_tree)"
"$VENV_AGENTOS" compile-adapters --json >/dev/null 2>&1 || \
  emit_result "T-ADP-PROBE-001" "FAIL" "second compile-adapters run failed"
H2="$(hash_tree)"

if [[ "$H1" == "$H2" && -n "$H1" ]]; then
  emit_result "T-ADP-PROBE-001" "PASS" "deterministic sha256=$H1"
else
  emit_result "T-ADP-PROBE-001" "FAIL" "drift: $H1 vs $H2"
fi
