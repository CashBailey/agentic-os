#!/usr/bin/env bash
# T-INT-001 — export markdown, re-import (idempotent), re-export, compare sha256.
set -uo pipefail
source "$(dirname "$0")/_common.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

SLUG="rt-probe-$(date +%s)"
# Create project + memory.
"$VENV_PY" - "$API_BASE" "$SLUG" <<'PY' >/dev/null
import json, sys, urllib.request as u
api, slug = sys.argv[1], sys.argv[2]
def post(path, body):
    req = u.Request(f"{api}{path}", method="POST",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type":"application/json"})
    return json.loads(u.urlopen(req, timeout=20).read().decode() or "{}")
post("/projects", {"slug": slug, "name": "RT", "root_path": "/tmp/rt"})
post(f"/projects/{slug}/memory", {"kind":"note","title":"t","body":"hello roundtrip","tags":[]})
PY

# 1st export.
EXP1="$TMP/exp1.tar"
curl -sS "$API_BASE/export/markdown?project=$SLUG" -o "$EXP1" || \
  emit_result "T-INT-001" "FAIL" "first export failed"
SHA1="$(sha256sum "$EXP1" | awk '{print $1}')"

# Untar and hash by-file content (tar header timestamps differ).
mkdir -p "$TMP/x1" && tar -xf "$EXP1" -C "$TMP/x1" 2>/dev/null || true
CONTENT_SHA_1="$(cd "$TMP/x1" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"

# Re-import (idempotent counts; we don't gate on counts, only the re-export).
curl -sS -X POST "$API_BASE/import/markdown" -F "file=@$EXP1" >/dev/null || true

# 2nd export.
EXP2="$TMP/exp2.tar"
curl -sS "$API_BASE/export/markdown?project=$SLUG" -o "$EXP2" || \
  emit_result "T-INT-001" "FAIL" "second export failed"
mkdir -p "$TMP/x2" && tar -xf "$EXP2" -C "$TMP/x2" 2>/dev/null || true
CONTENT_SHA_2="$(cd "$TMP/x2" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"

if [[ "$CONTENT_SHA_1" == "$CONTENT_SHA_2" ]]; then
  emit_result "T-INT-001" "PASS" "round-trip content sha256=$CONTENT_SHA_1 stable across export/import/export"
else
  emit_result "T-INT-001" "FAIL" "content sha differs: $CONTENT_SHA_1 vs $CONTENT_SHA_2"
fi
