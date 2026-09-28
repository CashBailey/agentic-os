#!/usr/bin/env bash
# T-SEC-002 — backend port listens on 127.0.0.1 only (no 0.0.0.0, no ::).
set -uo pipefail
source "$(dirname "$0")/_common.sh"

# Discover which port is up: prefer 8765, fall back to 8000.
PORT=""
for p in 8765 8000; do
  if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE ":${p}\$"; then
    PORT="$p"; break
  fi
done

if [[ -z "$PORT" ]]; then
  emit_result "T-SEC-002" "FAIL" "no backend port (8765 or 8000) is listening"
fi

LINES="$(ss -tln 2>/dev/null | awk -v p=":$PORT" '$4 ~ p { print $4 }')"
BAD="$(echo "$LINES" | grep -E '^(0\.0\.0\.0|\*|\[::\]):' || true)"
GOOD="$(echo "$LINES" | grep -E '^127\.0\.0\.1:' || true)"

if [[ -n "$BAD" ]]; then
  emit_result "T-SEC-002" "FAIL" "port $PORT listens on wildcard: $(echo "$BAD" | tr '\n' ' ')"
fi
if [[ -z "$GOOD" ]]; then
  emit_result "T-SEC-002" "FAIL" "port $PORT not bound to 127.0.0.1: $LINES"
fi

emit_result "T-SEC-002" "PASS" "port $PORT bound to 127.0.0.1 only"
