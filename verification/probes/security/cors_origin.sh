#!/usr/bin/env bash
# T-SEC-007 — CORS must not reflect arbitrary origins nor return wildcard ACAO.
set -uo pipefail
source "$(dirname "$0")/../_common.sh"

ID="T-SEC-007"

# Discover live port.
PORT=""
for p in 8765 8000; do
  if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE ":${p}\$"; then
    PORT="$p"; break
  fi
done

if [[ -z "$PORT" ]]; then
  emit_result "$ID" "FAIL" "no backend port (8765 or 8000) is listening; cannot test CORS"
fi

BASE="http://127.0.0.1:$PORT"
EVIL="http://evil.example"

PREFLIGHT="$(curl -sS -i -o - -X OPTIONS \
  -H "Origin: $EVIL" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Content-Type" \
  "$BASE/healthz" 2>/dev/null || true)"

GETRESP="$(curl -sS -i -o - -X GET \
  -H "Origin: $EVIL" \
  "$BASE/healthz" 2>/dev/null || true)"

check_response() {
  local label="$1" resp="$2"
  # status line: first "HTTP/x.y NNN ..."
  local status
  status=$(printf "%s" "$resp" | awk 'tolower($1) ~ /^http\// {print $2; exit}')
  # If status is 4xx/5xx (e.g. 400/403), browser won't proceed — that's fine.
  if [[ "$status" =~ ^(400|403|405|404)$ ]]; then
    echo "  $label: status=$status (blocked, OK)"
    return 0
  fi
  # Look for ACAO headers.
  if printf "%s" "$resp" | grep -i "^Access-Control-Allow-Origin:" | grep -iF "$EVIL" >/dev/null; then
    echo "  $label: REFLECTS evil origin"
    return 1
  fi
  if printf "%s" "$resp" | grep -i "^Access-Control-Allow-Origin:" | grep -F "*" >/dev/null; then
    echo "  $label: WILDCARD ACAO"
    return 1
  fi
  echo "  $label: status=$status, no ACAO leak"
  return 0
}

PRE_RES=$(check_response "preflight" "$PREFLIGHT") || true
GET_RES=$(check_response "get" "$GETRESP") || true

# Re-run capturing exit codes.
if ! check_response "preflight" "$PREFLIGHT" >/dev/null; then
  emit_result "$ID" "FAIL" "preflight reflected or wildcarded evil origin"
fi
if ! check_response "get" "$GETRESP" >/dev/null; then
  emit_result "$ID" "FAIL" "GET response reflected or wildcarded evil origin"
fi

emit_result "$ID" "PASS" "CORS does not reflect $EVIL and does not return wildcard ACAO"
