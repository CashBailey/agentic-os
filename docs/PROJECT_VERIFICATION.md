# Project Verification

Agentic OS is verified by a layered suite — a browser audit (Layer A, `e2e/`) plus CLI probes (Layer B, `verification/probes/`) — driven from a single entry point. The browser audit asserts only what a browser can truly observe; everything else (database rows, secret scrubbing, port binding, subprocess execution, byte-exact tarballs, vendor-token non-access) is asserted by a CLI probe. The principle behind this split lives in `docs/VERIFICATION_PHILOSOPHY.md`; the per-screen browser catalog lives in `browser_test_README.md`.

---

## Primary Entry Point

```bash
make verify
```

This invokes `scripts/run_project_verification.sh`, which runs the following steps in order, writing a timestamped summary to `verification/results/project-verification-<stamp>.md`:

1. `verification/probes/cli_help.sh` — `agentos` CLI surface (every subcommand emits `--help`).
2. `agentos validate` — canonical context (markdown + YAML + skills + workflows) parses and is internally consistent.
3. `agentos compile-adapters` — adapters compile cleanly into per-CLI output trees.
4. `verification/probes/execpolicy_check.sh` — Codex rules pass `codex execpolicy check`.
5. `verification/probes/generated_determinism.sh` — `compile-adapters` is byte-deterministic across two consecutive runs.
6. `verification/probes/install_adapter_subtree.sh` — `agentos install` creates the expected per-CLI subtrees in the user's home directory.
7. `pytest tests/phase1 tests/phase2 tests/integration` — CLI unit + integration tests.
8. `pytest tests/backend` — backend (FastAPI) unit tests.
9. `verification/probes/credential_blind.py` — backend never reads vendor token files (Claude / Gemini / Codex credential paths).
10. `verification/probes/redaction.py` — secrets are scrubbed before being persisted to storage or sent to an embedding model.
11. `verification/probes/ports_localhost.sh` — backend binds `127.0.0.1` only (never `0.0.0.0`).
12. `verification/probes/audit_emission.py` — a full approval lifecycle (create → request → approve → execute → finish) emits exactly the 5 expected audit events in order.
13. `verification/probes/markdown_roundtrip.sh` — DB → tarball export → fresh DB import is byte-equal at the markdown layer.
14. `npm --prefix e2e run audit` — Layer A browser audit (the catalog enumerated in `browser_test_README.md`).

A non-zero exit from any step fails the whole run. The summary file lists per-step status, duration, and the path to the captured evidence.

---

## Browser Audit Scope

The browser audit is restricted to the test IDs registered in `e2e/browser-audit-scope.mjs` and enumerated in `browser_test_README.md`. It may **not** claim coverage of anything below — these are explicitly out of browser scope and must be asserted by the named CLI probe.

- **DB state probes** → `verification/probes/audit_emission.py` (and friends).
- **Secret redaction** → `verification/probes/redaction.py`.
- **Port binding** → `verification/probes/ports_localhost.sh`.
- **Codex rule validity** → `verification/probes/execpolicy_check.sh`.
- **Adapter determinism** → `verification/probes/generated_determinism.sh`.
- **Tarball roundtrip** → `verification/probes/markdown_roundtrip.sh`.
- **Vendor-token-file non-access** → `verification/probes/credential_blind.py`.

If a browser test is tempted to assert any of these, move it. Faking a DB check through the UI produces noisy "blocked" results and erodes confidence in the catalog.

---

## Replaced Non-Browser Coverage

The table below names the test families that would otherwise have lived in the browser catalog but are intentionally replaced by CLI probes. Each row gives the original "would-have-been" browser ID, the probe that replaces it, and the primary evidence the probe captures.

| Replaced family                                                          | Replacement                                                  | Primary evidence                                       |
|--------------------------------------------------------------------------|--------------------------------------------------------------|--------------------------------------------------------|
| `T-SEC-credential-blind` — would require strace from a browser           | `verification/probes/credential_blind.py`                    | static source grep + monkeypatched open() tests        |
| `T-AUD-write-emission` — DB rows not visible to the browser              | `verification/probes/audit_emission.py`                      | DB query: count + ordered event-type sequence          |
| `T-SEC-port-binding` — browser sees only the one port it connected to    | `verification/probes/ports_localhost.sh`                     | `ss -tln` output, asserts `127.0.0.1:8765` only        |
| `T-POL-execpolicy-validity` — browser can't invoke the codex CLI         | `verification/probes/execpolicy_check.sh`                    | live `codex execpolicy check` exit status + stdout     |
| `T-ADP-determinism` — byte equality across runs not browser-observable   | `verification/probes/generated_determinism.sh`               | sha256 diff between two consecutive `compile-adapters` |
| `T-INT-export-import` — tarball roundtrip not browser-observable         | `verification/probes/markdown_roundtrip.sh`                  | sha256 of every entry in the export tarball            |
| `T-SEC-redaction` — DB content not visible to the browser                | `verification/probes/redaction.py`                           | round-trip injection: secret in → scrubbed value out   |
| `T-ADP-install-subtree` — filesystem outside the repo not browser-visible| `verification/probes/install_adapter_subtree.sh`             | `find` of `~/.claude`, `~/.gemini`, `~/.codex` post-install |

---

## Manual-Only Residual Checks

These cannot be automated cheaply and remain a human gate before a release:

- Real screen-reader walkthrough (NVDA on Windows, VoiceOver on macOS) of each route.
- `prefers-reduced-motion` behaviour validated against the actual OS setting (not just emulated via DevTools).
- True OS-level keyboard navigation behaviour in non-Chromium engines (Firefox, WebKit) — automated coverage uses Chromium only.
- Visual taste judgements — does the design feel right, is the information hierarchy correct, are the empty states humane?

These are tracked outside `make verify`; record them in the release checklist with the tester's initials and date.
