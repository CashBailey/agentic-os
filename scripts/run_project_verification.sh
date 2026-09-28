#!/usr/bin/env bash
# Agentic OS — full verification bundler (Layer A + Layer B).
# Writes a timestamped markdown summary under verification/results/.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
RESULTS_DIR="$ROOT_DIR/verification/results"
mkdir -p "$RESULTS_DIR"

SUMMARY_PATH="$RESULTS_DIR/project-verification-${STAMP}.md"
OVERALL_STATUS=0

cat >"$SUMMARY_PATH" <<EOF
# Project Verification

- Run at (UTC): ${STAMP}
- Working tree: ${ROOT_DIR}

| Step | Status | Command | Log |
| --- | --- | --- | --- |
EOF

run_step() {
  local slug="$1"
  local label="$2"
  local command="$3"
  local log_path="$RESULTS_DIR/${STAMP}-${slug}.log"
  local status="PASS"

  {
    printf '$ %s\n\n' "$command"
    bash -lc "$command"
  } >"$log_path" 2>&1 || status="FAIL"

  if [[ "$status" != "PASS" ]]; then
    OVERALL_STATUS=1
  fi

  printf '| %s | %s | `%s` | `%s` |\n' \
    "$label" "$status" "$command" "$log_path" >>"$SUMMARY_PATH"
}

# Layer B + Layer A steps, in execution order.
run_step "agentos-cli-help"        "agentos --help"            "verification/probes/cli_help.sh"
run_step "validate-canonical"      "agentos validate --json"   ".venv/bin/agentos validate --json"
run_step "compile-adapters"        "agentos compile-adapters"  ".venv/bin/agentos compile-adapters --json"
run_step "execpolicy-check"        "codex execpolicy check"    "verification/probes/execpolicy_check.sh"
run_step "generated-determinism"   "generated tree deterministic" "verification/probes/generated_determinism.sh"
run_step "install-adapter-subtree" "install-adapter subtrees"  "verification/probes/install_adapter_subtree.sh"
run_step "pytest-cli"              "pytest phase1/phase2/integration" "verification/probes/pytest_unit.sh"
run_step "pytest-backend"          "pytest backend"            "verification/probes/pytest_backend.sh"
run_step "credential-blind"        "credential-blind"          "verification/probes/credential_blind.py"
run_step "redaction"               "memory redaction"          "verification/probes/redaction.py"
run_step "ports-localhost"         "ports bound to 127.0.0.1"  "verification/probes/ports_localhost.sh"
run_step "audit-emission"          "audit chain emission"      "verification/probes/audit_emission.py"
run_step "markdown-roundtrip"      "markdown export/import roundtrip" "verification/probes/markdown_roundtrip.sh"
run_step "browser-audit"           "Layer A browser audit"     "npm --prefix e2e run audit"

OVERALL_LABEL="PASS"
[[ "$OVERALL_STATUS" -eq 0 ]] || OVERALL_LABEL="FAIL"

cat >>"$SUMMARY_PATH" <<EOF

## Overall

- Status: ${OVERALL_LABEL}
- Layer A artifacts: \`e2e/results/browser-audit-strict-*.md\`, \`e2e/results/browser-audit-strict-*.json\`
- Layer B logs: \`verification/results/${STAMP}-*.log\`
- Scope boundary: see \`docs/PROJECT_VERIFICATION.md\` for what is intentionally
  out-of-scope for the browser audit and is covered here by CLI probes.
EOF

printf 'Wrote %s\n' "$SUMMARY_PATH"
exit "$OVERALL_STATUS"
