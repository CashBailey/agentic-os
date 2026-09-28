> Adopted 2026-05-28. Implementation lives in e2e/ (Layer A) and verification/ (Layer B). Single entry: `make verify`.

# Verification Philosophy: CLI-First Verifiability

A portable, stack-agnostic template. Copy it into any repository and replace the
"Instantiation" column with your stack. Nothing here depends on a specific
language, framework, or browser tool.

---

## The principle

> Every capability the product exposes through a GUI can be driven and verified
> from a non-interactive command line, and every observable effect, both what
> the UI paints and the backend side effects it triggers, has a command-line
> assertion. The system is therefore fully exercisable by a script, a CI job, or
> an AI agent with no human in the loop, and every check produces durable
> evidence.

That paragraph is the whole idea. Everything below is the scaffolding that makes
it real.

---

## The problem it solves

Three failure modes of "we tested it in the browser":

1. **It needs a human.** Manual click-throughs do not run in CI and cannot be
   repeated cheaply.
2. **It only checks the paint, not the truth.** A green screen does not prove a
   row was written, an audit log fired, an email was sent, or a header was set.
   Most real bugs hide in that gap.
3. **It is not addressable.** "Login is broken" cannot be tied to a commit, a
   ticket, or a specific assertion.

CLI-first verifiability answers all three: scriptable, asserts backend truth,
and every check has a stable name.

---

## The two layers

This is the part most people miss. Driving the UI is only half of it.

**Layer A: drive and observe the GUI from code.** A headless browser driver plus
a small helper library so flows are scripted once and reused: log in as a role,
navigate, fill, click, screenshot, run an accessibility scan. Flows are written
once and called by name.

**Layer B: assert the effects the browser cannot show.** Command-line probes
against the things behind the UI:

- database state (row counts, status columns, foreign keys)
- audit and event logs (was the action recorded, with the right source?)
- outbound mail (query the test mail server)
- transport and headers (TLS redirect, HSTS, CSP, cookie flags)
- migrations and seed state, worker queues, object storage

Layer B is what turns "test the browser" into "verify the functionality."
Without it you are only checking pixels.

A single command bundles both layers and writes a timestamped summary. One
invocation, full-system confidence.

---

## The reusable components

| Component | What it gives you | Instantiation (fill in for your stack) |
|---|---|---|
| Stable, addressable test IDs | Every check referenceable from tickets, commits, automation | e.g. `T-AUTH-003` with a prefix legend |
| Headless browser driver + helper lib | Flows scripted once, reused everywhere | Playwright / Cypress / Selenium wrapper |
| CLI probes for non-visible state | Asserts backend truth, not just the screen | DB query, mail-server API, header check |
| Single-command bundling | One entrypoint runs the whole suite | `make verify`, `npm run verify`, CI job |
| Evidence capture on failure | Reproducible proof, not "it failed" | screenshot + HAR + query output |
| Regression pinning | Each shipped fix maps to the test(s) guarding it | commit -> test ID pinboard |
| Honest scope boundary | The browser suite only claims what a browser can truly prove; everything else is explicitly a CLI check | scoped audit + a verification doc |

The last row is a maturity signal. If forcing inbox, DB, or header checks
through the browser produces noisy "blocked" results, split them out into CLI
probes rather than faking them or marking them perpetually blocked.

---

## How to port it to a new repo

1. **Inventory the GUI surface.** List every route and the role(s) allowed.
   This becomes your route map and your test matrix.
2. **Pick a headless driver for your stack.** Wrap it in a thin helper lib so
   auth and navigation are one call.
3. **For each user-visible flow, name a test ID and write the script** (Layer A).
4. **For each flow, ask "what changed that the screen does not show?"** and
   write a CLI probe for it (Layer B): a DB query, a log check, a header check,
   a mail check.
5. **Bundle into one command** that runs the whole suite.
6. **Capture evidence on failure** automatically.
7. **Maintain a pinboard**: when you fix a bug, add the test ID that guards it
   and link the commit.
8. **Keep the scope boundary honest**: if a check cannot truly run in the
   browser, move it to a CLI probe rather than marking it perpetually blocked.

The principle and the recipe are stack-independent. The driver, the bundler, and
the probes are swappable; the two-layer structure and the seven properties stay
the same.

---

## One-liner for a README or a slide

> Every GUI action is scriptable headlessly, and every effect it causes, on
> screen and in the backend, has a command-line assertion. The product is fully
> verifiable by a script or an agent, regressions pin to commits, and every
> check leaves reproducible evidence.

---

## Why it sells

- An agent or CI verifies real end-to-end behavior with no human clicking.
- Regressions pin to the commit that introduced the guard.
- Evidence is reproducible: same command, same artifacts, every run.
- It often emerges from a constraint (interactive browser tooling failing in a
  given environment), and that same constraint is why the CLI-first approach
  ports cleanly: nothing in it depends on a human clicking.
