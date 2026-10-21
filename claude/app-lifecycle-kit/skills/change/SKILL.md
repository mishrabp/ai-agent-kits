---
name: change
description: Handles an incremental change to an existing app (a new feature, a modified behaviour, a bug fix, a removal or a refactor) by analysing its impact across requirements, design, code, tests and deployment, then updating only what is affected, in order. Use whenever the user asks to add, change, fix or remove something in an app that already has lifecycle state.
argument-hint: "<the change you want>"
allowed-tools: mcp__plugin_app-lifecycle_lifecycle
---

# Incremental change

Requested change: $ARGUMENTS

The lifecycle state already records what exists and why. Use it so that a change touches exactly what it
should and leaves nothing inconsistent.

## 1. Open the change
Call `status`. If a change is already open (`open_change`), ask whether to continue it or start a new one.
Otherwise clarify the request if needed (at most one round of questions), then call `start_change` with a
title, a description and a type: feature, fix, refactor, removal or nfr.

## 2. Analyse the impact
Delegate to the `app-lifecycle:impact-analyst` subagent with the change description. It uses `trace` and the
codebase to return the affected requirements, any new requirements needed, design sections, files and tests,
plus a plan and the risks. Record the result with `record_impact`.

Show the user the impact in a short table, with the plan and the risks, and get approval before changing anything.

## 3. Apply it top-down
Each layer is updated before the one below it. The state flags whatever is still out of date.
1. **Requirements:** update the affected requirements with `upsert_requirement` (pass `id`; changed criteria
   raise the revision). Add new ones (`status: "approved"` once the user has agreed in step 2). For removals, set
   `status: "retired"`.
2. **Design:** call `status`. Every section in `gaps.stale_design_sections`, plus any section for new
   requirements, is updated as in the design skill. Record a decision if the change alters an earlier one.
3. **Code:** build only the impacted parts, as in the build skill. Update `link_code`, and use `unlink_code` for
   deleted or moved files.
4. **Tests:** run the test workflow. It covers the changed and stale criteria, and runs the full suite for regressions.
5. **Deploy:** if the user wants to ship now, run the deploy workflow (it always asks for confirmation).

After each layer, call `status` to make sure its gaps are closed before you move on.

## 4. Close
Call `complete_change` with a one-paragraph summary. Report what changed in each layer, and the new
revision of each requirement.

## Rules
- Never change code for a behaviour change without first updating the requirement. A pure refactor or a fix
  that restores the specified behaviour is the exception: it keeps the requirement as it is.
- A bug fix should add a test that reproduces the bug, named after the criterion it violates.
