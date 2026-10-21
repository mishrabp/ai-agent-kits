---
name: build
description: Implements the designed requirements in code, one requirement at a time, following the recorded design, and links the code to the requirements. Use when the user asks to build, implement or code the app or a feature, or when status shows designed but unimplemented requirements.
argument-hint: "[REQ-ids to build, default: all designed but unimplemented]"
allowed-tools: mcp__plugin_app-lifecycle_lifecycle
---

# Build

Scope: $ARGUMENTS

## 1. Scope and context
- Call `status`. In scope: the IDs in the arguments, otherwise `gaps.unimplemented`. If a change is open, also
  include the files and requirements in its recorded impact.
- Read `.lifecycle/DESIGN.md` and the in-scope requirements in `.lifecycle/REQUIREMENTS.md`. The design is the
  contract you build against.
- If an in-scope requirement has no design, or its design is stale, run `/app-lifecycle:design` first.

## 2. Scaffold (new projects only)
If there's no code yet, create the project skeleton for the stack in the design: package manifest, source
layout, a test runner, a lint or format config, `.gitignore`, and a README with run and test commands. Prefer
the stack's standard tools, and keep dependencies few and well known.

## 3. Implement one requirement at a time
For each requirement, in priority order:
1. Implement exactly what its acceptance criteria require, following the components, data model and API
   contract in the design.
2. Add unit tests as you go. Name tests after the criterion they prove, by putting the criterion ID in the test
   name, for example `test("REQ-002.AC1 creating a todo returns 201", ...)`. The test phase relies on this.
3. Build or lint, and run the tests touched, to make sure the code compiles and runs.
4. Call `link_code` with the requirement ID and the source files that implement it. Don't include test files.

## 4. Don't drift from the design silently
If you must deviate from the design (a library doesn't work, the data model needs a field and so on), make
the change, then call `record_decision` explaining why, and update the affected section with `set_design_section`.

## 5. Hand off
Summarize what you built per requirement, and the files. The next step is `/app-lifecycle:test`. The code is
now marked as changed since the last test run.
