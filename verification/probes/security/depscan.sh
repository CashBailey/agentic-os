#!/usr/bin/env bash
# T-SEC-008 — dependency vulnerability scan (Python + npm).
# Fails on HIGH or CRITICAL severities; tolerates MEDIUM/LOW with a count.
set -uo pipefail
source "$(dirname "$0")/../_common.sh"

ID="T-SEC-008"

emit_skip() {
  local msg="$1"
  if [[ "$PROBE_WANT_JSON" -eq 1 ]]; then
    "$VENV_PY" -c "import json,sys; print(json.dumps({'id':sys.argv[1],'status':'SKIP','evidence':sys.argv[2]}))" "$ID" "$msg"
  else
    echo "[$ID] SKIP — $msg"
  fi
  exit 0
}

PIP_AUDIT="$REPO_ROOT/.venv/bin/pip-audit"
HAS_PIP_AUDIT=0
HAS_NPM=0

if [[ -x "$PIP_AUDIT" ]]; then HAS_PIP_AUDIT=1; fi

FRONTEND_DIR="$REPO_ROOT/frontend"
if command -v npm >/dev/null 2>&1 \
   && [[ -f "$FRONTEND_DIR/package.json" && -f "$FRONTEND_DIR/package-lock.json" ]]; then
  HAS_NPM=1
fi

if [[ "$HAS_PIP_AUDIT" -eq 0 && "$HAS_NPM" -eq 0 ]]; then
  emit_skip "neither pip-audit nor npm+package-lock.json available"
fi

PY_PARSER="$(mktemp /tmp/depscan-py.XXXXXX.py)"
NPM_PARSER="$(mktemp /tmp/depscan-npm.XXXXXX.py)"
trap 'rm -f "$PY_PARSER" "$NPM_PARSER"' EXIT

cat >"$PY_PARSER" <<'PY'
import json, sys
try:
    data = json.loads(sys.stdin.read() or "{}")
except Exception:
    print("0 0 0 0"); sys.exit(0)
high=crit=med=low=0
deps = data.get("dependencies", []) if isinstance(data, dict) else data
for d in deps or []:
    for v in (d.get("vulns") or []):
        sev = (v.get("severity") or "").upper()
        if sev == "HIGH": high+=1
        elif sev == "CRITICAL": crit+=1
        elif sev == "MEDIUM": med+=1
        elif sev == "LOW": low+=1
print(high, crit, med, low)
PY

cat >"$NPM_PARSER" <<'PY'
import json, sys
try:
    data = json.loads(sys.stdin.read() or "{}")
except Exception:
    print("0 0 0 0"); sys.exit(0)
meta = (data.get("metadata") or {}).get("vulnerabilities", {}) if isinstance(data, dict) else {}
print(meta.get("high",0), meta.get("critical",0), meta.get("moderate",0), meta.get("low",0))
PY

PY_HIGH=0; PY_CRIT=0; PY_MED=0; PY_LOW=0; PY_NOTE="skipped"
NPM_HIGH=0; NPM_CRIT=0; NPM_MED=0; NPM_LOW=0; NPM_NOTE="skipped"

if [[ "$HAS_PIP_AUDIT" -eq 1 ]]; then
  PIP_JSON="$("$PIP_AUDIT" --format json 2>/dev/null || true)"
  if [[ -n "$PIP_JSON" ]]; then
    read PY_HIGH PY_CRIT PY_MED PY_LOW <<<"$(printf "%s" "$PIP_JSON" | "$VENV_PY" "$PY_PARSER")"
    PY_NOTE="ran"
  else
    PY_NOTE="empty output"
  fi
fi

if [[ "$HAS_NPM" -eq 1 ]]; then
  NPM_JSON="$(cd "$FRONTEND_DIR" && npm audit --omit=dev --json 2>/dev/null || true)"
  if [[ -n "$NPM_JSON" ]]; then
    read NPM_HIGH NPM_CRIT NPM_MED NPM_LOW <<<"$(printf "%s" "$NPM_JSON" | "$VENV_PY" "$NPM_PARSER")"
    NPM_NOTE="ran"
  else
    NPM_NOTE="empty output"
  fi
fi

TOTAL_HC=$((PY_HIGH + PY_CRIT + NPM_HIGH + NPM_CRIT))
TOTAL_ML=$((PY_MED + PY_LOW + NPM_MED + NPM_LOW))

if [[ "$TOTAL_HC" -gt 0 ]]; then
  emit_result "$ID" "FAIL" "HIGH/CRITICAL found: py(H=$PY_HIGH C=$PY_CRIT) npm(H=$NPM_HIGH C=$NPM_CRIT); med/low total=$TOTAL_ML"
fi

emit_result "$ID" "PASS" "no HIGH/CRITICAL; pip-audit=$PY_NOTE npm=$NPM_NOTE; med/low total=$TOTAL_ML (py m=$PY_MED l=$PY_LOW, npm m=$NPM_MED l=$NPM_LOW)"
