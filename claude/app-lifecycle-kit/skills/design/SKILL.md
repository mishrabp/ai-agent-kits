---
name: design
description: Creates or updates the technical design (architecture, components, data model, API contract, UI, security, deployment, testing strategy) for the approved requirements, and records design decisions. Use after requirements are approved, when the user asks for a design or architecture, or when status shows undesigned requirements or stale design sections.
argument-hint: "[focus, e.g. data model or REQ-004]"
allowed-tools: mcp__plugin_app-lifecycle_lifecycle
---

# Design

Focus: $ARGUMENTS

## 1. Scope
Call `status`. You design for the approved requirements in `gaps.undesigned`, plus the sections listed in
`gaps.stale_design_sections` (their requirements changed after the section was written). If there's nothing to
do, say so and stop. If requirements are still drafts, ask the user to approve them first (`/app-lifecycle:requirements`).

## 2. Draft
Delegate to the `app-lifecycle:architect` subagent, telling it which requirement IDs and sections are in scope.
For an existing codebase it reads the code, so the design matches reality. It returns a proposal with sections
and decisions.

## 3. Review with the user
Present the proposal briefly: a few lines per section, plus every decision with the alternatives considered.
Ask the user to confirm the significant choices (stack, database, hosting, auth). Adjust as they ask.

## 4. Record it
- For each section: call `set_design_section` with the Markdown `content` and the `requirement_ids` it covers.
  Use the standard section names: overview, architecture, components, data_model, api, ui, security,
  non_functional, deployment, testing_strategy. Skip sections that don't apply, such as `ui` for an API.
  Every approved requirement must be covered by at least one section.
- For each significant choice: call `record_decision`. If you're replacing an old decision, pass `supersedes`.
- **APIs:** put the endpoint contract in the `api` section (method, path, request, response, errors). If the
  project wants an OpenAPI file, also write `openapi.yaml` and mention its path in the section.
- When updating a stale section, rewrite the whole section, keeping what is still true. `set_design_section`
  replaces it.
- If the stack is now decided, call `update_project` with `stack`.

## 5. Hand off
Point the user to `.lifecycle/DESIGN.md`. The next step is `/app-lifecycle:build`.
