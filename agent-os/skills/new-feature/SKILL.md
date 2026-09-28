---
name: new-feature
description: Drive a new feature from brainstorm to merge.
when_to_use:
  - User invokes /new-feature or asks to new feature
inputs:
  - context: current project state
outputs:
  - summary and any artifacts under agent-os/outputs/
safety:
  - respects file-policy.yaml protected paths
---

# Skill: new-feature

Drive a new feature from brainstorm to merge.

See workflow `workflows/new-feature.md` for steps.
