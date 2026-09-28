#!/usr/bin/env bash
# Run the AgenticOS k6 load-test suite.
# Exits 0 with BLOCKED message if k6 is not installed (so `make load` reports
# BLOCKED rather than hard-failing). Otherwise runs each scenario and exits
# non-zero if any failed.
set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v k6 >/dev/null 2>&1; then
  echo "BLOCKED: k6 not installed. See tests/load/README.md for install instructions."
  exit 0
fi

BASE_URL="${BASE_URL:-http://localhost:8000}"
PROJECT_SLUG="${PROJECT_SLUG:-default}"
export BASE_URL PROJECT_SLUG

echo "==> Load suite against ${BASE_URL} (project=${PROJECT_SLUG})"
echo

SCENARIOS=("audit.js" "memory_search.js" "approvals.js" "memory_leak.js")
declare -a NAMES=()
declare -a STATUSES=()
OVERALL=0

for script in "${SCENARIOS[@]}"; do
  echo "---- k6 run ${script} ----"
  if k6 run --quiet "${script}"; then
    NAMES+=("${script}")
    STATUSES+=("PASS")
  else
    rc=$?
    NAMES+=("${script}")
    STATUSES+=("FAIL(rc=${rc})")
    OVERALL=1
  fi
  echo
done

echo "================ k6 load suite summary ================"
printf "%-22s %s\n" "scenario" "status"
printf "%-22s %s\n" "----------------------" "------"
for i in "${!NAMES[@]}"; do
  printf "%-22s %s\n" "${NAMES[$i]}" "${STATUSES[$i]}"
done
echo "======================================================="

exit "${OVERALL}"
