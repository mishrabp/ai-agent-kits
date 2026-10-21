---
name: status
description: Shows the app's lifecycle dashboard (each requirement's stage from draft to deployed, gaps, stale tests or design, deploy readiness, the open change) and recommends the next step. Use when the user asks where the project stands, what's next, what's left, or about traceability for a requirement.
argument-hint: "[REQ-id for a full trace]"
allowed-tools: mcp__plugin_app-lifecycle_lifecycle
---

# Lifecycle status

Argument: $ARGUMENTS

1. If the argument is a requirement ID, call `trace` for it and show its whole chain: requirement → design
   sections and decisions → files → per-criterion tests → deployment → changes. Then stop.
2. Otherwise call `status`. If the project isn't initialized, suggest `/app-lifecycle:requirements` and stop.
3. Show a compact dashboard:
   - One line: project name, kind and stack.
   - A table with the requirement ID, title, priority, stage and criteria passing (such as `3/4`).
   - Gaps that aren't empty: drafts, undesigned, stale design sections, unimplemented, failing or untested
     criteria, and files changed since the last green run.
   - The last test run, the last deployment, and the open change, if there is one.
   - Deploy readiness, with the blockers.
4. End with the first item of `next_steps` as a recommendation, and offer to run it.

The full readable views are in `.lifecycle/REQUIREMENTS.md`, `DESIGN.md`, `TRACEABILITY.md` and `HISTORY.md`.
