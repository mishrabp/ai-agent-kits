---
name: requirements
description: Captures and maintains the requirements for an app, website or API by interviewing the user, then records them as testable requirements with acceptance criteria. Use when starting a new app or project, when the user describes what they want to build, or asks to add, review or approve requirements.
argument-hint: "[what you want to build]"
allowed-tools: mcp__plugin_app-lifecycle_lifecycle
---

# Capture requirements

User's input: $ARGUMENTS

You keep the requirements in the lifecycle state through the `lifecycle` MCP tools. Never write them to other files.

## 1. Check where the project stands
Call `status`.
- **Not initialized:** go to step 2.
- **Requirements already exist and some are approved:** this is an *incremental change*. Stop and run the
  `/app-lifecycle:change` workflow instead, so the change is tracked and its impact analysed. Exception: the user
  only wants to approve drafts or reword a draft; do that here with `upsert_requirement`.

## 2. Interview the user
Find out only what you can't infer. Ask in at most three rounds, using AskUserQuestion when it's available and
plain questions otherwise. Never ask about something the user has already told you.

1. **Product:** what it is, who uses it, and the problem it solves. Kind: web app, API, mobile, CLI and so on.
2. **Scope:** the core features for the first release (must), nice-to-haves (should/could), and what's explicitly out of scope.
3. **Constraints:** preferred stack, auth, data and storage, integrations, scale and performance, compliance,
   and the **deploy target** (Docker, Vercel, Fly.io, Azure, AWS, GCP, Kubernetes, or local only).

If the user says "you decide", propose sensible defaults and write them down as assumptions.

## 3. Write the requirements
- Call `init_project` (name, summary, kind, stack if known).
- Write one requirement per user-visible capability, as a user story in `description`:
  "As a <user>, I want <goal> so that <benefit>."
- Write 2 to 5 **acceptance criteria** for each, in Given/When/Then form. Each must be specific enough to become
  an automated test. Bad: "fast". Good: "Given 1,000 todos, when I list them, then the API responds in under 200 ms".
- Record non-functional requirements (performance, security, accessibility, availability) with `kind: non_functional`.
- Priorities: `must` is the first release; `should` and `could` come later.
- Save each one with `upsert_requirement` and `status: "draft"`.

## 4. Get approval
Show a compact table (ID, title, priority, criteria count), then the full criteria, then any assumptions.
Ask the user to approve or edit. Apply edits with `upsert_requirement` (pass the `id`). When the user approves,
set `status: "approved"` for each. Record the deploy target with `set_deploy_config` (`target` only).

## 5. Hand off
Tell the user the requirements are in `.lifecycle/REQUIREMENTS.md`, and that the next step is
`/app-lifecycle:design`. If they want the whole flow done end to end, carry on with design.
