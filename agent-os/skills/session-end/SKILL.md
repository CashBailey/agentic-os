---
name: session-end
description: Run end-of-session summary and handoff.
when_to_use:
  - User invokes /session-end or asks to session end
inputs:
  - context: current project state
outputs:
  - summary and any artifacts under agent-os/outputs/
safety:
  - respects file-policy.yaml protected paths
---

# Skill: session-end

Run end-of-session summary and handoff.

See workflow `workflows/session-end.md` for steps.
