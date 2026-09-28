---
name: security-review
description: Audit a diff or feature for security risks.
when_to_use:
  - User invokes /security-review or asks to security review
inputs:
  - context: current project state
outputs:
  - summary and any artifacts under agent-os/outputs/
safety:
  - respects file-policy.yaml protected paths
---

# Skill: security-review

Audit a diff or feature for security risks.

See workflow `workflows/security-review.md` for steps.
