#!/usr/bin/env bash
# T-ADP-PROBE-002 — install-adapter populates per-CLI subtrees with >=1 file each.
set -uo pipefail
source "$(dirname "$0")/_common.sh"

TARGET="/tmp/agentos-install-verify"
rm -rf "$TARGET"
mkdir -p "$TARGET"

"$VENV_AGENTOS" install-adapter --target "$TARGET" --mode copy --backup >/dev/null 2>&1 || \
  emit_result "T-ADP-PROBE-002" "FAIL" "install-adapter command failed"

MISSING=()
for sub in .claude .gemini .codex; do
  d="$TARGET/$sub"
  if [[ ! -d "$d" ]]; then MISSING+=("$sub (no dir)"); continue; fi
  cnt="$(find "$d" -type f | wc -l)"
  if [[ "$cnt" -lt 1 ]]; then MISSING+=("$sub (empty)"); fi
done

if [[ ${#MISSING[@]} -eq 0 ]]; then
  emit_result "T-ADP-PROBE-002" "PASS" ".claude/, .gemini/, .codex/ each contain >=1 file"
else
  emit_result "T-ADP-PROBE-002" "FAIL" "missing/empty: ${MISSING[*]}"
fi
