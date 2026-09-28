# UI Control Parity Gaps

Date: 2026-05-28

This document tracks `agentos ui` actions for which a `--via-ui` / `--via-api`
parity test cannot yet be written, and why.

## simulate-policy

`agentos ui simulate-policy` lacks `--via-ui` / `--via-api` flags entirely.
Its only options are `--tool`, `--action`, and `--args`. There is no toggle
to drive the browser button vs. hit the backend endpoint, so the two
execution paths can't be compared. A parity test cannot be written until
flag support is added to the `ui_control` CLI for `simulate-policy`.

## cancel-task

Subcommand does not exist in `agentos ui` (not present in
`agentos ui --help`). Action not yet exposed through the `ui_control` CLI.
A parity test cannot be written until the subcommand is added with both
`--via-ui` and `--via-api` flags.

## revoke-approval

Subcommand does not exist in `agentos ui` (not present in
`agentos ui --help`). Action not yet exposed through the `ui_control` CLI.
A parity test cannot be written until the subcommand is added with both
`--via-ui` and `--via-api` flags.

## archive-project

Subcommand does not exist in `agentos ui` (not present in
`agentos ui --help`). Action not yet exposed through the `ui_control` CLI.
A parity test cannot be written until the subcommand is added with both
`--via-ui` and `--via-api` flags.
