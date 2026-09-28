#!/usr/bin/env bash
# T-SEC-006 — backend bind address must be loopback only.
set -uo pipefail
source "$(dirname "$0")/../_common.sh"

ID="T-SEC-006"

PORT=""
for p in 8765 8000; do
  if ss -lntp 2>/dev/null | awk '{print $4}' | grep -qE ":${p}\$"; then
    PORT="$p"; break
  fi
done

if [[ -z "$PORT" ]]; then
  emit_result "$ID" "FAIL" "no backend port (8765 or 8000) is listening; cannot verify bind address"
fi

LINES="$(ss -lntp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p { print $4 }')"
BAD="$(echo "$LINES" | grep -E '^(0\.0\.0\.0|\*|\[::\]|\[::1\]):' || true)"
GOOD="$(echo "$LINES" | grep -E '^127\.0\.0\.1:' || true)"

if [[ -n "$BAD" ]]; then
  emit_result "$ID" "FAIL" "port $PORT listens on non-loopback address(es): $(echo "$BAD" | tr '\n' ' ')"
fi
if [[ -z "$GOOD" ]]; then
  emit_result "$ID" "FAIL" "port $PORT not bound to 127.0.0.1; listeners=$LINES"
fi

emit_result "$ID" "PASS" "port $PORT bound exclusively to 127.0.0.1"
