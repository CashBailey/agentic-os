#!/usr/bin/env bash
# T-SEC-005 — vendor-credential blindness under strace.
# Verifies that neither the backend nor `agentos auth-status` opens
# any of the forbidden vendor credential paths during normal operation.
set -uo pipefail
source "$(dirname "$0")/../_common.sh"

ID="T-SEC-005"
TRACE_BACKEND="/tmp/agentos-sec-cred-backend.strace"
TRACE_CLI="/tmp/agentos-sec-cred-cli.strace"

FORBIDDEN=(
  "$HOME/.codex/auth.json"
  "$HOME/.claude/.credentials.json"
  "$HOME/.config/gemini"
)

emit_skip() {
  # SKIP status (still exits 0 since it's not a failure).
  local msg="$1"
  if [[ "$PROBE_WANT_JSON" -eq 1 ]]; then
    "$VENV_PY" -c "import json,sys; print(json.dumps({'id':sys.argv[1],'status':'SKIP','evidence':sys.argv[2]}))" "$ID" "$msg"
  else
    echo "[$ID] SKIP — $msg"
  fi
  exit 0
}

if ! command -v strace >/dev/null 2>&1; then
  emit_skip "strace not installed"
fi

if [[ ! -x "$VENV_AGENTOS" ]]; then
  emit_result "$ID" "FAIL" "agentos CLI not found at $VENV_AGENTOS"
fi

BACKEND_BIN="$REPO_ROOT/.venv/bin/agentos-backend"

# --- Backend trace ---------------------------------------------------------
BACKEND_PID=""
if [[ -x "$BACKEND_BIN" ]]; then
  rm -f "$TRACE_BACKEND"
  # Run under its own process group so we can clean up children.
  setsid strace -f -e trace=openat -o "$TRACE_BACKEND" "$BACKEND_BIN" \
    >/tmp/agentos-sec-cred-backend.out 2>&1 &
  BACKEND_PID=$!

  # Wait up to 8s for /healthz on 8765 or 8000.
  PORT_UP=""
  for _ in $(seq 1 40); do
    for p in 8765 8000; do
      if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE ":${p}\$"; then
        PORT_UP="$p"; break 2
      fi
    done
    sleep 0.2
  done

  # Tear down the backend (process group).
  if [[ -n "$BACKEND_PID" ]]; then
    kill -TERM -"$BACKEND_PID" 2>/dev/null || kill -TERM "$BACKEND_PID" 2>/dev/null || true
    sleep 0.5
    kill -KILL -"$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
fi

# --- CLI trace -------------------------------------------------------------
rm -f "$TRACE_CLI"
strace -f -e trace=openat -o "$TRACE_CLI" \
  "$VENV_AGENTOS" auth-status >/tmp/agentos-sec-cred-cli.out 2>&1 || true

# --- Grep both traces ------------------------------------------------------
LEAKS=()
for trace in "$TRACE_BACKEND" "$TRACE_CLI"; do
  [[ -s "$trace" ]] || continue
  for path in "${FORBIDDEN[@]}"; do
    if grep -F -- "\"$path" "$trace" >/dev/null 2>&1; then
      LEAKS+=("$(basename "$trace"):${path}")
    fi
  done
  # Also catch gemini dir prefix matches.
  if grep -E "\"$HOME/\.config/gemini" "$trace" >/dev/null 2>&1; then
    LEAKS+=("$(basename "$trace"):~/.config/gemini*")
  fi
done

# De-dup.
if [[ ${#LEAKS[@]} -gt 0 ]]; then
  UNIQ=$(printf "%s\n" "${LEAKS[@]}" | sort -u | tr '\n' ' ')
  emit_result "$ID" "FAIL" "vendor credentials opened: $UNIQ"
fi

emit_result "$ID" "PASS" "no vendor credential openat across backend+CLI strace"
