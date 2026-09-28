# AgenticOS Release Checklist

This checklist gates every tagged release. It is deliberately manual: CI
catches regressions, but only a human can catch "the docs lied", "the UI
feels broken", or "the audit story doesn't make sense to a new engineer".

Do not skip sections. If you skip, write `SKIPPED - <reason>` in the Notes
column so the next reviewer can see what was not exercised.

Target time: ~30 minutes end to end (10 min smoke + 5 min UI + 10 min audit
read + 5 min sign-off).

---

## Section 1 - Fresh-install smoke

Goal: prove a stranger following the README on a clean machine reaches a
working system. No shortcuts. No "I already have it cached locally".

Use a **clean VM or fresh container** (suggested: a throwaway Ubuntu 24.04
VM, or `docker run --rm -it ubuntu:24.04 bash` with `git`/`curl` installed).
Do **not** mount your dev workspace, do **not** copy your venv, do **not**
paste commands from memory. Follow `README.md` literally, top to bottom.

| # | Step | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 1.1 | Open `README.md` in a browser on the clean VM. | Renders. No broken images/links to internal paths. | | |
| 1.2 | Install system prerequisites exactly as listed (Python version, Postgres version, any apt/brew packages). | Each command succeeds. README lists every prereq actually needed. | | |
| 1.3 | Clone the repo at the release tag (`git clone ... && git checkout vX.Y.Z`). | Clean clone. | | |
| 1.4 | Run the install command(s) from the README (e.g. `pip install -e .[dev]` or `make install`). | Completes without manual edits. No "you also need to..." surprises. | | |
| 1.5 | Run the first-time setup command from the README (DB migration / seed / `agentos init` / equivalent). | Completes. State directory created where README says it will be. | | |
| 1.6 | Run the "hello world" / smoke command from the README. | Output matches what README promises. | | |
| 1.7 | Start the backend per README. | Listens on the documented port. No tracebacks. | | |
| 1.8 | Start the frontend per README. | Loads in a browser at the documented URL. | | |
| 1.9 | Stop everything per README ("how to shut down" section). | Clean shutdown. No orphan processes / stuck ports. | | |
| 1.10 | Anything you had to figure out that README did **not** say. | None. | | List every undocumented step here. |

Hard fail if any row in 1.1-1.9 required reading source code or asking
someone. The README is a contract.

---

## Section 2 - Five-minute UI exploration

Goal: catch the things tests cannot - feel, polish, and accessibility.
Spend at least 5 minutes clicking around the frontend like a new user.
Use the items below as a watch-list, not a script.

For each item: open the app, exercise the interaction, and write your
observation. "Looks fine" is acceptable only if you actually tried it.

| # | Watch for | What to do | Pass/Fail | Notes |
|---|-----------|------------|-----------|-------|
| 2.1 | **Theme-toggle jank.** | Toggle light/dark at least 5 times in a row. Watch for: flash of wrong theme, layout shift, controls that don't re-color, charts that stay in the old palette, icons that invert badly. | | |
| 2.2 | **Copy clarity.** | Read every label, button, empty state, and error message on the first two screens. Anything jargon-y, ambiguous, or "obviously written by an engineer to themselves" is a fail. | | |
| 2.3 | **Color contrast in a dim room.** | Dim your monitor (or move to a darker spot) and check: body text, secondary/muted text, disabled buttons, focus rings, error/warn states. Anything you have to squint at fails WCAG-ish smell test. | | |
| 2.4 | **FOUC on first paint.** | Hard-refresh (Ctrl-Shift-R) the main route. Watch the first 500ms: unstyled text flash, layout jumping as fonts/CSS load, theme flipping from default to user preference. | | |
| 2.5 | **Keyboard navigation for all primary actions.** | Unplug the mouse (or just don't touch it). Tab through the main screen. Every primary action (submit, cancel, open, save, navigate) must be reachable and activatable via keyboard alone, with a visible focus ring at every stop. | | |
| 2.6 | **Empty / loading / error states.** | Trigger an empty list, a slow load (throttle network in devtools), and a forced error. Each state should look intentional, not like a bug. | | |
| 2.7 | **Mobile-ish width.** | Resize to ~390px wide. Nothing should clip, overlap, or require horizontal scroll for primary actions. (If mobile is explicitly out of scope, write "OUT OF SCOPE" and move on.) | | |

---

## Section 3 - Audit-chain readability

Goal: confirm the audit trail tells a coherent story to a new engineer.
The point of the audit chain is post-hoc comprehension; if a fresh reader
can't follow it, it has failed its purpose regardless of what tests pass.

Pick **3 random recent audit chains** (do not cherry-pick the prettiest
ones). Suggested method: take the last 20 runs, roll a die / pick by ID
modulo something, commit to those three before reading any of them.

For each chain, read it end-to-end as if you'd never seen this system,
then answer: **does this story make sense to a new engineer?**

| # | Chain ID / timestamp | Story makes sense? | What's missing or confusing? | Pass/Fail |
|---|----------------------|--------------------|------------------------------|-----------|
| 3.1 | | | | |
| 3.2 | | | | |
| 3.3 | | | | |

A "Pass" requires all three to be Yes. One "Yes, but I had to grep source
to understand step N" is a Fail - file an issue against the audit emitter.

---

## Section 4 - Sign-off

Every row above must have a Pass/Fail. This table records who attested.
No release ships without a fully signed Section 4.

| Section | Item | Tester | Date | Pass/Fail | Notes |
|---------|------|--------|------|-----------|-------|
| 1 | Fresh-install smoke (all of 1.1-1.10) | | | | |
| 2 | UI exploration (all of 2.1-2.7) | | | | |
| 3 | Audit-chain readability (3.1-3.3) | | | | |
| - | Release approver (final go/no-go) | | | | |

**Release tag:** `vX.Y.Z`
**Commit SHA:** `__________________________________`
**CI run (test-matrix) URL:** `__________________________________`
**Date released:** `YYYY-MM-DD`

If any row is `Fail`, the release does not ship. Open issues for each
failure, link them in Notes, and re-run this checklist after fixes.
