#!/usr/bin/env bash
# run_all.sh - Aggregate runner for security probes (T5b)
# Runs every other *.sh probe in this directory, captures status, prints summary,
# exits 0 if all PASS, 1 if any FAIL.

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
SELF="$(basename -- "${BASH_SOURCE[0]}")"

declare -a NAMES
declare -a STATUSES
declare -a CODES

overall_rc=0

shopt -s nullglob
probes=("$SCRIPT_DIR"/*.sh)
shopt -u nullglob

if [[ ${#probes[@]} -eq 0 ]]; then
    echo "No probes found in $SCRIPT_DIR" >&2
    exit 1
fi

echo "=============================================="
echo " Security Probe Aggregator (T5b)"
echo " Directory: $SCRIPT_DIR"
echo "=============================================="
echo

for probe in "${probes[@]}"; do
    name="$(basename -- "$probe")"
    [[ "$name" == "$SELF" ]] && continue

    echo "---- Running: $name ----"
    bash "$probe"
    rc=$?
    if [[ $rc -eq 0 ]]; then
        status="PASS"
    else
        status="FAIL"
        overall_rc=1
    fi
    echo "---- $name: $status (exit=$rc) ----"
    echo

    NAMES+=("$name")
    STATUSES+=("$status")
    CODES+=("$rc")
done

# Summary table
echo "=============================================="
echo " Summary"
echo "=============================================="
printf "%-30s %-8s %-6s\n" "PROBE" "STATUS" "EXIT"
printf "%-30s %-8s %-6s\n" "------------------------------" "--------" "------"
for i in "${!NAMES[@]}"; do
    printf "%-30s %-8s %-6s\n" "${NAMES[$i]}" "${STATUSES[$i]}" "${CODES[$i]}"
done
echo "=============================================="
if [[ $overall_rc -eq 0 ]]; then
    echo "OVERALL: PASS"
else
    echo "OVERALL: FAIL"
fi
echo "=============================================="

exit $overall_rc
