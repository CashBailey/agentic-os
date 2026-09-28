# Agentic OS — Architecture

> Generated 2026-05-28. The interactive knowledge graph behind this document
> lives in [`graphify-out/`](../graphify-out/) — open `graph.html` in a browser,
> read `GRAPH_REPORT.md` for the full audit trail, or query `graph.json`
> (GraphRAG-ready). Built with `/graphify` over 223 code files + 39 canonical
> docs → **1353 nodes / 2383 edges / 99 communities** (≈26.7× token reduction
> per query vs. reading the corpus raw).

Agentic OS is a **tool-neutral substrate for AI coding agents**: one canonical
body of context/memory/skills/workflows/policies under `agent-os/` is *compiled*
into deterministic per-CLI adapters (`CLAUDE.md` / `GEMINI.md` / `AGENTS.md` and
matching `.claude/` / `.gemini/` / `.codex/` subtrees). An optional localhost-only
FastAPI backend persists projects/memory/approvals/audit; an optional React
dashboard and a `agentos ui` CLI (with byte-for-byte CLI↔GUI parity) sit on top.

## The nine clusters

The graph's community detection recovered these as distinct, low-cross-talk
clusters. Each maps to a source location and one or more graphify communities.

### 1. CLI (`agentos_cli/`)
The `agentos` command surface. An argparse root (`cli.py`) **auto-discovers**
command modules in `commands/` via `pkgutil` + a `register(subparsers)`
convention — drop a file in `commands/`, get a subcommand. Commands: `sync`,
`validate`, `auth-status`, `compile-adapters`, `install-adapter`, `ui`.
- Source: `agentos_cli/cli.py`, `agentos_cli/commands/`
- Graph: community "CLI Commands" / "CLI Core: Context Loader & Sync" (C3),
  "UI CLI Command & Shortcuts" (C13)

### 2. Canonical agent-os source (`agent-os/`)
The single source of truth that everything compiles *from*: `context/global/*`
(developer profile, coding standards, security boundaries, tool/communication
prefs), `skills/`, `workflows/`, `templates/`, `policies/*.yaml`,
`adapters/{claude,gemini,codex}.yaml`. `generated/` holds the compiled output
(gitignored).
- Source: `agent-os/**`
- Graph: "Canonical agent-os Context" (C16), "Compiled Adapters", "agent-os
  Workflows/Skills/Templates"

### 3. Adapter compiler (`agentos_cli/core/`)
The heart of the system — a **compile-target pattern**: load policies + adapter
configs + canonical context, run each per-CLI emitter, write to
`agent-os/generated/{cli}/**`. **Determinism is enforced**: files sorted by path,
JSON `sort_keys=True`, *no timestamps ever emitted*, a sha256 `_source_hash` over
inputs, and write-only-if-changed. Re-runs are byte-identical (there is a
"generated determinism" probe).
- Source: `agentos_cli/core/adapter_compiler.py`, `claude_adapter.py`,
  `gemini_adapter.py`, `codex_adapter.py`, `context_loader.py`, `policy.py`,
  `templates.py`
- Graph: "Adapter Compiler" (C7), god node `compile_all()`

### 4. Backend (`backend/app/`)
Localhost-only FastAPI service (refuses non-loopback bind). 16 routers
(projects, memory, approvals, audit, decisions, context, adapters, policies,
skills, workflows, sessions, events, exports, worker, health, auth_status),
SQLAlchemy async models + Pydantic schemas + services (audit, redaction,
policy_eval, embeddings, markdown_io), Alembic migration `0001_initial`, and a
durable SKIP-LOCKED worker.
- Source: `backend/app/` (api/, models/, schemas/, services/, db/, worker.py,
  main.py)
- Graph: "Backend Models & Audit" (C1), "Backend API: Adapters & Approvals"
  (C4), "Backend App & Test Fixtures" (C14), "DB Migrations & Worker" (C9)

### 5. Frontend (`frontend/src/`)
**React 19 + Vite + TanStack Query + Zustand + React Router + Tailwind** (not
SvelteKit — the README was corrected). Routes: Dashboard, Approvals, Audit,
Memory, Context, Policies, Skills, Adapters; a `components/ui/` design system;
`state/theme.tsx` (dark default, light toggle). *Note:* the graph under-counts
this cluster — the AST extractor yields sparse nodes for JSX-heavy `.tsx`, so the
React layer is thinner in the graph than in reality (39 source files).
- Source: `frontend/src/`
- Graph: "Frontend Icons (React)" (C21) + API-client nodes (`fetchReadiness`,
  `isNetworkError`, `describeError`) folded into C0

### 6. E2E (`e2e/`)
Playwright "Layer A" browser audit (Node `.mjs`): per-route flows (dashboard,
approvals, audit, memory, context, policies, skills, adapters), a11y (axe-core),
theme, and a smoke sweep, plus a strict scope-checked runner.
- Source: `e2e/flows/`, `e2e/lib/`, `e2e/run-browser-audit.mjs`
- Graph: "E2E Browser Audit (Layer A)" (C2), "E2E CLI Tests & API Endpoints" (C10)

### 7. Tests (`tests/`)
14 tiers: `backend/` (DB-backed API), `contract/`, `property/` (hypothesis),
`chaos/`, `security/`, `integration/`, `e2e/`, `ui_cli/`, `ui_control/` (CLI↔GUI
parity), `unit/`, `upgrade/`, `load/` (k6), `phase1/`, `phase2/`.
- Source: `tests/**`, `conftest.py`
- Graph: woven through most communities (tests cluster with the module they
  exercise) — notably C0, C5, C9, C18 ("UI Parity Tests")

### 8. Safety (`agentos_cli/safety/` + policy hooks)
Fail-closed guarantees: `path_guard.py` (path-traversal + symlink-escape
rejection, protected-path denylist for `.env`/`*.pem`/`*.key`/`agent-os/private/**`),
`shell_parse.py`, and the generated pre-tool-use / pre-file-write hooks that
return `deny` on malformed input. Backend mirrors this with `policy_eval` and a
NUL/control-char rejection middleware.
- Source: `agentos_cli/safety/`, `backend/app/services/policy_eval.py`,
  `agent-os/policies/*.yaml`
- Graph: "Policy Hooks & Shell Parsing (Safety)" (C6), "Policy Evaluation" (C19),
  god node `evaluate_shell()`

### 9. Memory (`backend` memory subsystem + `agent-os/memory/`)
Persistent memory items with **secret redaction applied before storage *and*
before embedding** (`redact()` strips AWS/GitHub/OpenAI keys, bearer tokens,
`key=value` secrets), local `sentence-transformers` embeddings (lazy-loaded,
dim 384) into pgvector, and canonical `agent-os/memory/global/*` lessons/prefs.
- Source: `backend/app/api/memory.py`, `services/redaction.py`,
  `services/embeddings.py`, `models/memory.py`, `agent-os/memory/`
- Graph: "Embeddings & Redaction (Memory)" (C12), god node `redact()`

## Cross-cutting observations

**God nodes** (most-connected core abstractions): `get()`/`post()` (HTTP probe
helpers, shared across the test/verification tiers), `redact()` (memory safety),
`evaluate_shell()` (policy safety), `run()` (CLI entry), `ORMBase` (schema base).

**Surprising connections** the graph surfaced (cross-document, INFERRED): the
README's *credential-blind posture* ↔ `security-boundaries.md`; the *protected-path
denylist* ↔ the bug-fix skill's safety note; the backend's *no-auth / 127.0.0.1*
stance ↔ the browser-audit's *no-auth surface* assumption. These confirm the
safety story is stated consistently across code, canonical context, and docs.

## Using the graph

```bash
# interactive
open graphify-out/graph.html

# ask the graph (BFS context, DFS to trace a path)
graphify query "how does the adapter compiler stay deterministic"
graphify path "Adapter Compiler" "Canonical agent-os Context"
graphify explain "redact"

# refresh after code changes (incremental, AST-only is free)
graphify --update .
```
