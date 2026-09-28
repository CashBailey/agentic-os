---
name: session-start
description: Run start-of-session orientation.
when_to_use:
  - User invokes /session-start or asks to session start
inputs:
  - context: current project state
outputs:
  - summary and any artifacts under agent-os/outputs/
safety:
  - respects file-policy.yaml protected paths
---

# Skill: session-start

Run start-of-session orientation.

See workflow `workflows/session-start.md` for steps.
