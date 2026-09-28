# Agentic OS

**Status:** alpha · personal-use · single-developer build  
**License:** Proprietary — all rights reserved (see `LICENSE`)

## What it is

Agentic OS is a tool-neutral substrate for AI coding agents. It maintains
**one canonical body of context, memory, skills, workflows, and policies**
under `agent-os/` and compiles deterministic per-CLI adapter outputs
(`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, plus matching `.claude/`, `.gemini/`,
`.codex/` subtrees) so the same project rules apply whether you drive it with
Claude Code, Gemini CLI, or Codex CLI. An optional FastAPI backend (Phase 3)
adds persistent memory, an approval queue, and an audit log; a React
frontend (Phase 4) visualizes them. Everything runs locally; nothing phones
home.

## Quick start

```bash
cd agentic-os
pip install -e .
agentos sync              # generates CLAUDE.md / GEMINI.md / AGENTS.md
```

To wire the generated adapters into another repo:

```bash
agentos compile-adapters --project <slug>
agentos install-adapter --project <slug> --target /path/to/repo --mode copy --backup
```

`--mode dry-run` is the default; pass `--mode copy` or `--mode symlink` to
actually write.

## Authentication posture

Agentic OS is **credential-blind**. The default and recommended authentication
path is your **vendor subscription/account login**:

- **Claude Code:** run `claude` and `/login` with your Claude.ai
  (Pro/Max/Team/Enterprise) account.
- **Gemini CLI:** run `gemini` and choose "Login with Google" with your
  Google AI Pro/Ultra account.
- **Codex CLI:** run `codex login` and choose "Sign in with ChatGPT".

Agentic OS never reads, parses, copies, or stores vendor auth caches
(`~/.codex/auth.json`, `~/.claude/.credentials.json`, `~/.config/gemini/**`,
etc.) and never prompts for vendor passwords. The only thing it does is run
`<cli> --version` to detect install state.

API-key environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GEMINI_API_KEY`, `GOOGLE_API_KEY`) are allowed **only** for explicit
automation / CI use. If any are set when you run `agentos auth-status`, the
report flags that CLI as `api_key_mode` with a warning that the env var may
override your subscription login.

## Safety guarantees

- **Dry-run by default.** `agentos sync` and `agentos install-adapter` both
  default to `--mode dry-run`; nothing is written until you opt in.
- **Backup before overwrite.** With `--backup` (default on for
  `install-adapter`), every existing destination file is renamed to
  `<name>.bak.YYYYMMDD-HHMMSS` before being replaced. Backups apply to both
  top-level instruction files (CLAUDE.md, etc.) and per-CLI subtree files
  (e.g. `.claude/hooks/pre_tool_use.py`).
- **Path-traversal rejection.** Destinations containing `..` segments that
  resolve outside `--target` are rejected via canonical-path comparison.
- **Symlink-escape rejection.** Symlinks whose resolved target leaves
  `--target` are treated as traversal and rejected.
- **Protected-path denylist.** Writes matching `.env`, `*.pem`, `*.key`,
  `agent-os/private/**`, or any vendor auth cache path are refused even
  inside an otherwise-valid target.
- **Hook fail-closed.** Generated hook scripts return `decision=deny` on
  malformed input rather than allowing the tool call through.

## CLI surface

| Subcommand            | Purpose |
| --------------------- | ------- |
| `agentos sync`        | Generate `CLAUDE.md` / `GEMINI.md` / `AGENTS.md` from `agent-os/` context. |
| `agentos validate`    | Validate directory layout, template presence, and YAML front-matter of canonical files. |
| `agentos auth-status` | Report install + auth-mode state (`installed`, `api_key_mode`, `not_installed`, `unknown`) for claude/gemini/codex without touching their credential stores. |
| `agentos compile-adapters` | Render the per-CLI adapter subtrees (`.claude/`, `.gemini/`, `.codex/`) plus top-level MDs into `agent-os/generated/`. |
| `agentos install-adapter`  | Install rendered adapter files into a target repo. Supports `--mode {dry-run,copy,symlink}`, `--backup`, `--cli {claude,gemini,codex,all}`. |

All write commands honor the safety guarantees above and emit JSON with
`--json` for scripting.

## Phase 3 backend (optional)

A localhost-only FastAPI service that persists projects, memory items,
approval requests, and audit events to Postgres. **No API keys, no remote
calls, no inbound exposure beyond `127.0.0.1`.**

```bash
cd backend
docker compose up -d db
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If port 8000 is occupied on your machine, substitute `--port 8765` (or any
free local port). The service refuses to bind a non-loopback address.

## Frontend (optional)

React dashboard (React 19 + Vite + TanStack Query + Zustand + React Router +
Tailwind) that surfaces auth status, the approval queue, audit events, and
memory items. Dark theme is the default; light theme is one toggle away.

```bash
cd frontend
npm install
npm run dev
```

## UI control CLI (`agentos ui`)

Every browser-controllable surface is reachable from the command line via
`agentos ui …`, so CLI and GUI are interchangeable for daily-driver work.
A single persistent Chromium daemon (started once) keeps each subsequent
command fast (~300 ms) and operates on the same tab.

```bash
# Lifecycle
agentos ui start [--headed]      # launches the persistent daemon
agentos ui status                # running pid / current route / theme
agentos ui logs --tail 50        # tail browser daemon log
agentos ui stop                  # kills daemon, removes session file

# Primitives (each supports --json)
agentos ui nav /memory
agentos ui click "role=button[name=Approve]"
agentos ui fill "input[name=query]" "audit chain"
agentos ui eval "document.documentElement.getAttribute('data-theme')"
agentos ui route                 # prints just the pathname (e.g. /memory)
agentos ui screenshot --route /audit --out shot.png

# High-level shortcuts (parity: --via-ui is the default; --via-api skips the UI)
agentos ui theme light|dark|toggle
agentos ui project demo
agentos ui approve 42  --via-ui   # click the row's Approve button
agentos ui approve 42  --via-api  # POST /approvals/42/decide directly
agentos ui deny    42  --via-api --reason "wrong project"
agentos ui compile-adapters --via-ui
agentos ui simulate-policy --tool shell --action write --args '{"path":"/tmp/x"}'
agentos ui search-memory "deploy"
agentos ui list-routes
agentos ui smoke                 # drive every route + screenshot per theme
```

Output is human-friendly by default; `--json` returns a single JSON object
on stdout (errors as `{"error": "...", "code": N}` on stderr). Exit codes:
`0` ok, `1` action failed, `2` no session, `3` frontend unreachable, `4`
backend unreachable.

A parity test (`tests/ui_control/test_parity.py`) asserts that
`--via-ui` and `--via-api` emit byte-identical audit-event sequences:

```bash
make ui-test
```

Make targets: `ui-start`, `ui-stop`, `ui-status`, `ui-logs`, `ui-smoke`,
`ui-test`.

## Repository layout

```
agentic-os/
├── agent-os/             # canonical context, memory, skills, workflows, templates, policies
│   └── generated/        # compiled per-CLI adapters (gitignored)
├── agentos_cli/          # the `agentos` Python CLI
│   ├── commands/         # sync, validate, auth-status, compile-adapters, install-adapter
│   ├── core/             # context loader, markdown renderer, path utilities
│   └── safety/           # path-guard, protected-path denylist
├── backend/              # FastAPI service (Phase 3, optional)
├── frontend/             # React + Vite dashboard (Phase 4, optional)
├── tests/                # phase1/, phase2/, backend/, integration/
└── pyproject.toml
```

## Project status

Alpha, single-author, intended for personal use. Interfaces may change
without notice. Use the dry-run modes liberally and review JSON output
before applying changes to any repository you care about.
