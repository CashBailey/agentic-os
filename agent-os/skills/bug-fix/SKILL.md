---
name: bug-fix
description: Investigate and fix a reported bug.
when_to_use:
  - User invokes /bug-fix or asks to bug fix
inputs:
  - context: current project state
outputs:
  - summary and any artifacts under agent-os/outputs/
safety:
  - respects file-policy.yaml protected paths
---

# Skill: bug-fix

Investigate and fix a reported bug.

See workflow `workflows/bug-fix.md` for steps.
