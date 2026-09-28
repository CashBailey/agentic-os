#!/usr/bin/env bash
# Common helpers for shell probes. Source from probes.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_PY="$REPO_ROOT/.venv/bin/python"
VENV_AGENTOS="$REPO_ROOT/.venv/bin/agentos"
API_BASE="${AGENTOS_API_BASE:-http://127.0.0.1:8765}"

PROBE_WANT_JSON=0
for arg in "$@"; do
  if [[ "$arg" == "--json" ]]; then PROBE_WANT_JSON=1; fi
done

emit_result() {
  # emit_result <id> <status> <evidence>
  local id="$1" status="$2" evidence="$3"
  if [[ "$PROBE_WANT_JSON" -eq 1 ]]; then
    "$VENV_PY" -c "import json,sys; print(json.dumps({'id':sys.argv[1],'status':sys.argv[2],'evidence':sys.argv[3]}))" "$id" "$status" "$evidence"
  else
    echo "[$id] $status — $evidence"
  fi
  if [[ "$status" == "PASS" ]]; then exit 0; else exit 1; fi
}
