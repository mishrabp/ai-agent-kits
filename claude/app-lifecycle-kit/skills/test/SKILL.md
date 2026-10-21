---
name: test
description: Writes or updates automated tests for every acceptance criterion, runs the full suite, and records the per-criterion results in the lifecycle state. Use when the user asks to test or verify the app, after building, or when status shows untested, failing or stale tests.
argument-hint: "[REQ-ids, default: everything untested, stale or failing]"
allowed-tools: mcp__plugin_app-lifecycle_lifecycle
---

# Test

Scope: $ARGUMENTS

## 1. Scope
Call `status`. In scope: `gaps.untested` and `gaps.failing` criteria, plus every criterion of a requirement whose
files appear in `gaps.changed_files`. Narrow this down if the arguments name requirement IDs. The whole suite
always runs, so regressions anywhere are caught.

## 2. Delegate
Hand the work to the `app-lifecycle:test-engineer` subagent, listing the criterion IDs in scope. It:
- writes or updates one or more tests per criterion, with the criterion ID in the test name;
- runs the **full** suite with the project's test command;
- maps the results back to criterion IDs and calls `record_test_run` itself;
- returns a summary, plus details of any failures.

## 3. Handle the result
- **All green:** report the pass count and criteria coverage. If the project is deploy-ready (`status` → `deploy_ready`),
  the next step is `/app-lifecycle:deploy`.
- **Failures:** show each failing criterion with the error. Decide whether the bug is in the **code** (fix it,
  following the build rules) or the **test** (fix the test). Never weaken a test so that it passes against the
  acceptance criterion. Then run this skill again until it's green. If a criterion itself is wrong, that's a requirement
  change: use `/app-lifecycle:change`.
