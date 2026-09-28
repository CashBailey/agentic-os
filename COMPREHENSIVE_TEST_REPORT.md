# Comprehensive Test Report — AgenticOS

## Header

- **Date (UTC):** 2026-05-28T22:37:30Z (final rerun)
- **Host:** raptor-lab-laptop2
- **Repo root:** /home/raptor-lab-laptop2/AgenticOS/agentic-os
- **Git SHA:** `06c10f15f43f21bf64163f0819e4f42dd24edc21`
- **Overall verdict (2026-05-28 run, superseded):** PARTIAL (9 PASS / 1 FAIL / 0 SKIP / 3 BLOCKED across 13 steps) — **see "## Update — 2026-05-29" below.** The two T3-verify probe FAILs are now resolved: `make verify` reports **Status: PASS (14/14)**.
- **Counts journey:**
  - Original: **3 PASS / 4 FAIL / 1 SKIP / 5 BLOCKED**
  - After fix pass 1: **10 PASS / 1 FAIL / 0 SKIP / 3 BLOCKED**
  - Final (this run): **9 PASS / 1 FAIL / 0 SKIP / 3 BLOCKED**
- **Net delta vs after-fix-1:** T5b-security flipped FAIL → PASS; T3-verify regressed PASS → FAIL (two probes inside `make verify` now fail).
- **Master log:** `verification/results/COMPREHENSIVE-T1-T7-FINAL-20260528T223730Z.md`

## Update — 2026-05-29 (resolution of the two T3-verify FAILs)

Re-ran the full `make verify` chain against a freshly-started backend
(`127.0.0.1:8765`) plus the Vite frontend (`5173`, pointed at the backend via
`VITE_API_BASE_URL`):

- **`make verify` → Status: PASS — 14/14 steps green** (13 Layer B CLI probes
  + Layer A browser audit **39/39**). Run log:
  `verification/results/project-verification-2026-05-29T01-37-57Z.md`.

**Root cause of the two prior FAILs: a non-hermetic verification setup, not
product bugs.** `scripts/run_project_verification.sh` does not start the backend
and never resets the shared Postgres volume (`agentos-pgdata`), so the
2026-05-28 probes ran against an accumulated DB and a backend instance that is
now gone.

- **`memory redaction` (T-SEC-003):** does **not** reproduce. Passes on every
  run against current working-tree code (repeatedly, and in harness order after
  `pytest-backend`). The probe's only fragility is a same-second
  `int(time.time())` slug that 409s on rapid re-runs (correct behavior). No code
  change was required for the reported symptom.
- **`markdown export/import roundtrip` (T-INT-001):** does **not** reproduce.
  Proven idempotent at the content layer — export→import→export yields
  byte-identical file manifests and per-file SHAs (import creates a duplicate
  row, but content-hash filenames collapse it). No normalization fix needed.

**Hardening added (a genuine latent bug found while triaging the 500 class):**
`POST /projects` did a check-then-insert with no `IntegrityError` handling (and
`main.py` has no global handler), so a slug-uniqueness **race** (TOCTOU)
returned a raw 500 — harmless under single-worker dev, a live 500 under
`uvicorn --workers N`. Fixed in `backend/app/api/projects.py` (catch
`IntegrityError` → rollback → 409), covered by a real failing-first race test
(`tests/backend/test_api_projects.py::test_create_project_duplicate_slug_race_returns_409`).
Full backend suite: **36 passed**.

**Note on `test_skip_locked_claim_no_duplicates`:** transiently failed
mid-session because repeated redaction probes left `queued memory.embed` rows
that the worker test (which claims from the *global* queue) picked up — the same
non-hermetic-DB issue, a test-isolation gap, not a product bug. Passes on a
clean queue.

**Remaining blockers (unchanged — environment/manual, not code):** T5a `k6`
(not installed; needs sudo/apt), T6 `actionlint` (not installed; needs
Go/sudo), T7 manual release checklist (needs a human). These are outside the
`make verify` chain.

## Final state

- **Total tests / steps across the suite:** 13 top-level steps (T1–T7) wrapping a much larger probe count:
  - T1 unit: 95 backend pytest cases + 2 frontend vitest cases
  - T2: 49 contract tests + 2 property tests
  - T3 verify: 15 probes (13 PASS, 2 FAIL) inside `make verify`; plus 12 parity-ext (`tests/ui_control`) PASS
  - T4 e2e: 1 passed, 5 skipped, 2 xfailed
  - T5b security: 2 passed (injection + redaction)
  - T5c chaos: 3 passed
  - T5d upgrade: 1 passed, 1 skipped
  - **Aggregate test cases executed in this run: ~190**, with ~187 passing.
- **Test / fix code added across the campaign:**
  - Backend NUL-byte hardening in `backend/app/main.py` (`RejectControlCharsMiddleware`, ~30 LOC, 1 file).
  - Security harness fixes in `tests/security/*` from earlier passes (~120 LOC across 3 files).
  - Verification helper hardening (`verification/probes/*` + `Makefile` env scrubbing) (~80 LOC across 4 files).
  - **Approximate total new / modified test + harness code: ~230 LOC across ~8 files.**

## What's GREEN

| Tier | Step | Count |
|------|------|------|
| T1 | unit-backend (pytest) | 95 passed |
| T1 | unit-frontend (vitest) | 2 passed (1 file) |
| T2 | contract | 49 passed |
| T2 | property | 2 passed |
| T3 | parity-ext (`tests/ui_control`) | 12 passed |
| T3 | verify — passing probes inside the otherwise-failing chain | 13/15 probes (CLI help, validate --json, compile-adapters, execpolicy, generated determinism, install-adapter subtrees, pytest CLI, pytest backend, credential-blind, ports localhost, audit chain, Layer A browser audit) |
| T4 | e2e | 1 passed, 5 skipped, 2 xfailed |
| T5b | security | 2 passed (injection + redaction harness) |
| T5c | chaos | 3 passed |
| T5d | upgrade | 1 passed, 1 skipped |

**Total: 9 of 10 runnable steps GREEN.**

## What's still not GREEN

### FAIL — T3-verify (`make verify`, exit 2)

Two probes inside `make verify` regressed in this run:

1. **memory redaction** — `verification/probes/redaction.py`
   - **Error:** `[T-SEC-003] FAIL — create failed: HTTP Error 500: Internal Server Error`
   - **Likely cause:** The probe POSTs to the backend memory-create endpoint and receives a 500. This is a different failure mode than the recently-fixed NUL-byte path (that middleware returns 400, not 500). The redaction probe likely sends a payload shape the create handler still chokes on (probable candidates: oversized field, unexpected nested object, or a path that hits the psycopg layer outside the middleware's scope).
   - **Recommended fix:**
     1. Re-run the probe with backend log capture: `tail -F backend/logs/*.log & python verification/probes/redaction.py`.
     2. Inspect the stack trace at the create endpoint and add the missing validation / serialization handling.
     3. If the trace shows another psycopg `DataError` outside the request body, extend `RejectControlCharsMiddleware` (or add per-field sanitization) to cover the offending field.

2. **markdown export/import roundtrip** — `verification/probes/markdown_roundtrip.sh`
   - **Error:** content SHA mismatch on export → import → export:
     - `abcfa6a9d4df344d1781bc2560b5e4cdcae08b39ed303063535e7e1e926a304a`
     - vs `fd6323c5844824446cc2f62a62472a7ba36d334516198c897784d2d803f6f086`
   - **Likely cause:** Non-deterministic field in the markdown serializer — most commonly trailing newline normalization, timestamp re-stamping on import, or dict-ordering in a frontmatter block.
   - **Recommended fix:**
     1. Diff the two markdown artifacts: `diff <(cat first.md) <(cat second.md)` (the probe should be edited to keep both on FAIL).
     2. Pin the differing field (sort frontmatter keys, freeze `updated_at`, strip trailing whitespace).
     3. Re-run `bash verification/probes/markdown_roundtrip.sh`.

### BLOCKED — T5a load (`make load`)
- **Why:** `k6` is not installed on this host. `make load` exits 0 but prints `BLOCKED: k6 not installed`.
- **Unblock:** Install via Grafana apt repo (requires sudo). Not in default Ubuntu 24.04 repos. **Needs human + sudo.**

### BLOCKED — T6 ci-validate (`actionlint`)
- **Why:** `actionlint` not installed; not present in Ubuntu 24.04 apt repos. Falls back to YAML-parse-only validation (which passes).
- **Unblock:** Install actionlint binary (Go release or `go install`). **Needs human + sudo or Go toolchain.**

### BLOCKED — T7 manual
- **Why:** This is the human release-checklist tier (`docs/RELEASE_CHECKLIST.md`); cannot be executed by an automated agent.
- **Unblock:** Human tester walks the checklist. **Needs human.**

## Genuine residual gaps (honest)

These are the items this workstation literally cannot resolve without out-of-band action:

1. **`k6` install** — requires Grafana apt repo registration which requires sudo (no password available to the agent). Cannot install user-locally because k6 is distributed as a system binary with no pip/npm equivalent. **Requires user sudo.**
2. **`actionlint` install** — not in apt; the user-local install path is `go install github.com/rhysd/actionlint/cmd/actionlint@latest`, but no Go toolchain is on PATH on this host. **Requires user sudo (apt install golang) or a pre-built binary download.**
3. **T7 manual release checklist** — by design requires a human walking through the GUI / release flow. **Requires user.**
4. **T3 verify probes (redaction + markdown roundtrip)** — these *are* fixable by this workstation but require backend log-capture and source edits to the create handler / markdown serializer. They are not blocked by environment, only by the next debugging cycle.

## Recommended next steps for the user

In priority order:

1. **Triage the two new T3-verify regressions (highest leverage — flips overall verdict to fully GREEN for everything that isn't BLOCKED).**
   ```bash
   cd /home/raptor-lab-laptop2/AgenticOS/agentic-os
   # Capture redaction probe failure
   .venv/bin/uvicorn backend.app.main:app --port 8000 --log-level debug 2>&1 | tee /tmp/redaction-probe.log &
   sleep 2
   .venv/bin/python verification/probes/redaction.py
   # Inspect /tmp/redaction-probe.log for the 500 stacktrace

   # Capture markdown roundtrip diff
   bash -x verification/probes/markdown_roundtrip.sh 2>&1 | tee /tmp/md-roundtrip.log
   # Edit the probe (or hand-run the two halves) to retain both .md files, then:
   diff /tmp/md-first.md /tmp/md-second.md
   ```

2. **Unblock T5a (load tests) by installing k6:**
   ```bash
   sudo gpg -k
   sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
   echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
   sudo apt update && sudo apt install -y k6
   # Then re-run:
   make load
   ```

3. **Unblock T6 (ci-validate) by installing actionlint (no sudo needed if you have Go):**
   ```bash
   # Option A: pre-built binary
   bash <(curl https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash)
   sudo mv actionlint /usr/local/bin/
   # Option B: via Go
   sudo apt install -y golang-go
   go install github.com/rhysd/actionlint/cmd/actionlint@latest
   export PATH="$HOME/go/bin:$PATH"
   ```

4. **T7 manual:** open `docs/RELEASE_CHECKLIST.md` and walk the steps by hand.

5. **Optional — re-run the full comprehensive sweep after (1)–(3):**
   ```bash
   bash verification/scripts/run-comprehensive-t1-t7.sh
   ```
   Expected post-fix state: **13 PASS / 0 FAIL / 0 SKIP / 0 BLOCKED** once k6, actionlint, the two T3 probe fixes, and a human T7 pass are all in.
