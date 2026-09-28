# Agentic OS Browser Test README

This document is the browser-executable end-to-end test catalog for Agentic OS. Every test has a stable ID; the SMOKE set runs on every build, and the full matrix runs before any release. The catalog is paired with a CLI probe suite (see `docs/PROJECT_VERIFICATION.md`); both layers are executed together by `make verify`. The philosophy that motivates the split is in `docs/VERIFICATION_PHILOSOPHY.md`.

---

## 0. How to use this document

- **Scope.** UI-driven checks only. Anything not observable in a browser tab (DB rows, secret redaction, port binding, subprocess execution, byte-exact tarballs, vendor-token file access) lives in `docs/PROJECT_VERIFICATION.md` and is covered by `verification/probes/`. `make verify` runs the whole thing.
- **Environment.** Frontend at `http://localhost:5173`, backend at `http://127.0.0.1:8765` (note: ports were originally 8000/5173 in the blueprint; backend has been moved to 8765 to avoid local conflicts — substitute as needed if your run uses a different port). Postgres runs in the docker container `agentos-db` exposed on `localhost:5432`.
- **Status flags.** Every row is tracked as `PASS`, `FAIL`, `BLOCKED`, or `N/A`.
- **Ordering.** Top-down. Later tests assume earlier tests in the same area passed; SMOKE assumed before anything else.
- **Durability on FAIL.** Capture (a) a screenshot via `e2e/lib/browser.mjs:saveFailureArtifacts`, (b) the offending network request/response, and (c) any DB row that was (or should have been) written. Layer A captures (a) automatically; (b) and (c) are appended by the tester when relevant.
- **No auth surface.** Agentic OS is single-user local; there is no login, no role matrix, no session-management test family. Skip auth patterns from upstream reference catalogs.

---

## 1. Pre-flight

Bring the full stack up before running anything in this document:

```bash
cd /home/raptor-lab-laptop2/AgenticOS/agentic-os
docker compose -f docker-compose.yml up -d db
cd backend && env -u PYTHONPATH .venv/bin/alembic upgrade head
cd backend && nohup env -u PYTHONPATH .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765 >/tmp/agentos-backend.log 2>&1 &
cd frontend && npm install && npm run dev &
```

Confirm health before continuing:

- `http://localhost:5173/` → HTTP 200, no console errors
- `http://127.0.0.1:8765/healthz` → HTTP 200, JSON `{"status":"ok"}`
- `docker ps | grep agentos-db` shows the database container `Up`

If any of these fail, every test in this document is **BLOCKED**; do not record per-test PASS until the pre-flight is clean.

### 1.1 Authoritative route map

This table must mirror `frontend/src/App.tsx`. If the app's router drifts from this table, fix the table — the running app is authoritative.

| Path         | Screen             | Source file                                       | Notes                                                  |
|--------------|--------------------|---------------------------------------------------|--------------------------------------------------------|
| `/`          | Dashboard          | `frontend/src/routes/Dashboard.tsx`               | Landing route; CLI readiness + KPIs.                   |
| `/context`   | Context Editor     | `frontend/src/routes/Context.tsx`                 | Markdown docs (global + per-project).                  |
| `/memory`    | Memory             | `frontend/src/routes/Memory.tsx`                  | FTS + semantic search.                                 |
| `/adapters`  | Adapters           | `frontend/src/routes/Adapters.tsx`                | CLI adapter cards + diff viewer.                       |
| `/policies`  | Policies           | `frontend/src/routes/Policies.tsx`                | YAML editor + decision simulator.                      |
| `/skills`    | Skills + Workflows | `frontend/src/routes/Skills.tsx`                  | Two-tab view.                                          |
| `/approvals` | Approvals          | `frontend/src/routes/Approvals.tsx`               | Pending queue with SSE live update.                    |
| `/audit`     | Audit              | `frontend/src/routes/Audit.tsx`                   | Event table with cursor pagination + SSE live-tail.    |
| `*`          | 404 / NotFound     | `frontend/src/App.tsx` catch-all                  | Renders a "route not found" panel.                     |

### 1.2 Recommended tooling

- **Manual:** Chromium or Chrome with DevTools open (Network + Console panels visible).
- **Automated:** Playwright lives in `e2e/`; run with `make verify-layer-a` or `npm --prefix e2e run audit`.
- **Accessibility:** axe-core via `e2e/lib/browser.mjs:runAxe`.
- **Performance:** Lighthouse run manually; not part of the automated audit.
- **Screenshot CLI:** `make screenshot ROUTE=/audit THEME=dark` writes a PNG into `verification/results/screenshots/`.

---

## 2. SMOKE (P0 critical path)

The SMOKE set must pass on every build before any other test is attempted. These IDs are locked and must match those registered in `e2e/browser-audit-scope.mjs`.

| ID          | Test                                          | Expected                                                                                            |
|-------------|-----------------------------------------------|-----------------------------------------------------------------------------------------------------|
| `T-SMK-001` | Boot frontend at `/`                          | App renders, no console errors, top bar + sidebar visible.                                          |
| `T-SMK-002` | All 8 routes navigable                        | `/`, `/context`, `/memory`, `/adapters`, `/policies`, `/skills`, `/approvals`, `/audit` each render without error. |
| `T-SMK-003` | Dark theme is default on fresh load           | With empty `localStorage`, `document.documentElement.dataset.theme === 'dark'`.                     |
| `T-SMK-004` | Theme toggle cycles dark ↔ light              | Clicking the top-bar toggle flips `data-theme` between `dark` and `light`.                          |
| `T-SMK-005` | Project switcher renders                      | Top-bar dropdown lists projects fetched from `GET /projects`.                                       |

---

## 3. Per-area browser tests

### 3.1 Dashboard (`T-DASH-NNN`)

| ID           | Test                                              | Expected                                                                                  |
|--------------|---------------------------------------------------|-------------------------------------------------------------------------------------------|
| `T-DASH-001` | CLI readiness cards render 3 items                | Cards for `claude`, `gemini`, `codex` each show a state pill (installed / missing).       |
| `T-DASH-002` | Backend offline banner                            | When the API is unreachable, a banner appears and KPIs degrade gracefully.                |
| `T-DASH-003` | Pending approvals KPI                             | *(PLANNED — see §5)* The KPI matches the count returned by `GET /approvals?status=pending`. |

### 3.2 Context editor (`T-CTX-NNN`)

| ID          | Test                                            | Expected                                                                                |
|-------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| `T-CTX-001` | Document list groups by scope                   | Two groups render: `global` and `project`.                                              |
| `T-CTX-002` | Selecting a doc loads its content               | Editor populates with markdown from `GET /context/{id}`.                                |
| `T-CTX-003` | Edit + Save round-trip                          | Saving issues `PUT /context/{id}`; re-fetch returns the new body.                       |
| `T-CTX-004` | Dirty-state badge                               | *(PLANNED — see §5)* Badge appears while unsaved, clears immediately on save.            |

### 3.3 Memory (`T-MEM-NNN`)

| ID          | Test                                            | Expected                                                                                |
|-------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| `T-MEM-001` | List renders memory items                       | Initial `GET /memory` rows render with kind + summary.                                  |
| `T-MEM-002` | FTS search filters the list                     | Typing in the search box debounces and issues `GET /memory?q=...`.                      |
| `T-MEM-003` | Kind dropdown filters                           | Selecting a kind constrains the query by `kind=`.                                       |
| `T-MEM-004` | Semantic search button                          | *(PLANNED — see §5)* "Semantic search" submits and renders ranked results.              |
| `T-MEM-005` | Create new memory item via modal                | *(PLANNED — see §5)* Modal submit issues `POST /memory`; new row appears.               |

### 3.4 Adapters (`T-ADP-NNN`)

| ID          | Test                                            | Expected                                                                                |
|-------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| `T-ADP-001` | Three CLI cards render                          | Cards for `claude`, `gemini`, `codex` each show last-generated timestamp.               |
| `T-ADP-002` | "Compile now" enqueues a task                   | Click issues `POST /adapters/compile`; worker row appears via `GET /adapters/tasks`.    |
| `T-ADP-003` | Diff panel renders                              | *(PLANNED — see §5)* Selecting a generated file shows a side-by-side diff.              |

### 3.5 Policies (`T-POL-NNN`)

| ID          | Test                                            | Expected                                                                                |
|-------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| `T-POL-001` | Four policy files listed                        | The four canonical policy files appear in the left rail.                                |
| `T-POL-002` | Selecting a file loads YAML                     | Editor populates with YAML from `GET /policies/{name}`.                                 |
| `T-POL-003` | Simulator returns decision + matched_rule       | Submitting a request through the simulator returns both `decision` and `matched_rule`.  |

### 3.6 Skills + Workflows (`T-SKL-NNN`)

| ID          | Test                                            | Expected                                                                                |
|-------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| `T-SKL-001` | Skills list renders                             | First tab lists skills from `GET /skills`.                                              |
| `T-SKL-002` | Workflows tab switches and renders              | Second tab lists workflows from `GET /workflows`.                                       |

### 3.7 Approvals (`T-APP-NNN`)

| ID          | Test                                            | Expected                                                                                |
|-------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| `T-APP-001` | Pending approvals table renders                 | Rows from `GET /approvals?status=pending` are visible.                                  |
| `T-APP-002` | Approve button transitions row                  | Clicking Approve issues `POST /approvals/{id}/approve`; row state becomes `approved`.   |
| `T-APP-003` | Deny button transitions row                     | Clicking Deny issues `POST /approvals/{id}/deny`; row state becomes `denied`.           |
| `T-APP-004` | SSE live update                                 | A new approval pushed to the backend appears without page reload.                       |

### 3.8 Audit (`T-AUD-NNN`)

| ID          | Test                                            | Expected                                                                                |
|-------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| `T-AUD-001` | Audit events table renders                      | Columns `timestamp`, `type`, `actor` populated from `GET /audit`.                       |
| `T-AUD-002` | Cursor pagination advances                      | "Next" advances the cursor and loads the next page; "Prev" returns.                     |
| `T-AUD-003` | Payload expand reveals JSON                     | Expanding a row reveals the full JSON payload, pretty-printed.                          |
| `T-AUD-004` | SSE live-tail toggle                            | *(PLANNED — see §5)* Toggling live-tail prepends new rows in real time.                 |

### 3.9 Theming (`T-THM-NNN`)

| ID          | Test                                            | Expected                                                                                |
|-------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| `T-THM-001` | Dark default with empty localStorage            | First load with no stored preference sets `data-theme="dark"`.                          |
| `T-THM-002` | Toggle to light                                 | Toggle changes `data-theme="light"` and persists to `localStorage`.                     |
| `T-THM-003` | Reload persists chosen theme                    | After reload the previously chosen theme is reapplied.                                  |
| `T-THM-004` | Toggle back to dark                             | Toggle returns `data-theme="dark"` and persists.                                        |

### 3.10 Accessibility (`T-A11Y-NNN`)

| ID             | Test                                            | Expected                                                                                |
|----------------|-------------------------------------------------|-----------------------------------------------------------------------------------------|
| `T-A11Y-001`   | Dashboard axe scan                              | 0 critical violations from `runAxe()` on `/`.                                           |
| `T-A11Y-002`   | axe `/context`                                  | 0 critical violations.                                                                  |
| `T-A11Y-003`   | axe `/memory`                                   | 0 critical violations.                                                                  |
| `T-A11Y-004`   | axe `/adapters`                                 | 0 critical violations.                                                                  |
| `T-A11Y-005`   | axe `/policies`                                 | 0 critical violations.                                                                  |
| `T-A11Y-006`   | axe `/skills`                                   | 0 critical violations.                                                                  |
| `T-A11Y-007`   | axe `/approvals`                                | 0 critical violations.                                                                  |
| `T-A11Y-008`   | axe `/audit`                                    | 0 critical violations.                                                                  |

---

## 4. Out of browser scope

Non-browser checks live in `docs/PROJECT_VERIFICATION.md` and the `verification/probes/` directory. If a check cannot truly be observed in a browser tab (DB row, port bind, secret scrub, subprocess execution, byte-exact tarball, vendor-token file access), it belongs in a CLI probe — not in this catalog.

---

## 5. Planned IDs (catalog-only, not yet in automated scope)

These IDs are documented capabilities that the Layer A harness does not yet exercise. They are intentionally NOT in `e2e/browser-audit-scope.mjs` so the catalog cross-check stays green. To activate, add a flow that asserts the behavior and register the ID in the scope file.

| ID | Reason not yet automated |
|---|---|
| `T-DASH-003` | Requires seed approvals + KPI scrape; deferred until a deterministic seed fixture exists. |
| `T-CTX-004` | Dirty-state visual indicator design pending. |
| `T-MEM-004` | Local embeddings extra not installed on the audit host; semantic-search button currently returns empty hits. |
| `T-MEM-005` | "New memory" modal flow not yet wired. |
| `T-ADP-003` | Diff viewer renders only when `adapter_generations` has ≥2 rows for a CLI; seed flow pending. |
| `T-AUD-004` | SSE live-tail toggle exists; deterministic event injection from the harness needs a backend test hook. |

## 5. Planned IDs (catalog-only, not yet in automated scope)

These IDs are documented capabilities the Layer A harness does not yet exercise. They are intentionally NOT in `e2e/browser-audit-scope.mjs` so the catalog cross-check stays green. To activate, add a flow that asserts the behavior and register the ID in the scope file.

| ID | Reason not yet automated |
|---|---|
| `T-DASH-003` | Requires deterministic seed approvals fixture. |
| `T-CTX-004` | Dirty-state visual indicator design pending. |
| `T-MEM-004` | Local embeddings extra not installed on the audit host; semantic-search currently returns empty hits. |
| `T-MEM-005` | "New memory" modal flow wiring pending. |
| `T-ADP-003` | Diff viewer renders only when ≥2 generations exist; seed flow pending. |
| `T-AUD-004` | Live-tail toggle works manually; deterministic backend event injection hook pending. |
