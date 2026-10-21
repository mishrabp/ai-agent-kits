# app-lifecycle-kit

A Claude Code plugin that takes an app, website or API through **requirements → design → build → test →
deploy**. It keeps a persistent, traceable record of every phase, so later incremental changes touch exactly
what they should and leave nothing out of date.

All the code is Python (standard library only, 3.9 or newer, run as `python3`). It's shared through the
[ai-agent-kits](https://github.com/mishrabp/ai-agent-kits) marketplace.

## How it keeps context

Each project gets a `.lifecycle/` folder. Commit it with the code.

```
.lifecycle/
  state.json          ← single source of truth (written only through the lifecycle MCP tools)
  REQUIREMENTS.md     ← generated views, regenerated on every change, so they read well in PRs
  DESIGN.md
  TRACEABILITY.md     ← REQ → design → code → tests → deployment, plus deploy readiness and next steps
  HISTORY.md          ← change requests, deployments, test runs
```

The state links every layer to the one above it:

```
REQ-002 (revision 2) ── acceptance criteria REQ-002.AC1..AC3
   ├─ design sections: api, data_model   (written against REQ-002 revision 2)
   ├─ decisions: DEC-003
   ├─ code: src/notes.js, src/server.js
   ├─ tests: REQ-002.AC1 ✓  REQ-002.AC2 ✓  REQ-002.AC3 ✓   (verified at revision 2)
   └─ deployed: DEP-004 at revision 2
```

Staleness is worked out from this record, not left for Claude to remember:

| Event | What becomes stale |
|---|---|
| A requirement's title, description or criteria change (revision +1) | its design sections, its test results, its deployment |
| Any source file is edited (PostToolUse hook) | "tests stale": deploy is blocked until a green full run |
| A test run records a failure | deploy is blocked |
| Code changes after the last deployment | "undeployed changes" |

Every session starts with a short status summary. A **SessionStart hook** injects it: the project, the stage
counts, the open change, stale items and the next steps. So a brand-new session, or a teammate's session, picks up
where the last one stopped.

## What's in it

| Piece | Files | Role |
|---|---|---|
| **Connector** (MCP server `lifecycle`) | `src/lifecycle.py` (entry point), `src/server.py`, `src/state.py`, `src/render.py`, `src/mcp_stdio.py` | 16 tools: `status`, `trace`, `get_state`, `init_project`, `upsert_requirement`, `set_design_section`, `record_decision`, `link_code`, `record_test_run`, `set_deploy_config`, `record_deployment`, `start_change`, `record_impact`, `complete_change`, ... Validates input and returns the next steps after every write |
| **Hooks** | `hooks/hooks.json` → `src/lifecycle.py session-start` / `track-edit` | `SessionStart` puts the status into context; `PostToolUse` (Edit/Write) records changed files |
| **Skills** | `skills/*/SKILL.md` | `/app-lifecycle:requirements`, `design`, `build`, `test`, `deploy`, `change`, `status` |
| **Agents** | `agents/*.md` | `architect` (proposes the design), `test-engineer` (writes tests mapped to criteria, runs the suite, records results), `impact-analyst` (impact of a change, read-only) |
| **Deploy recipes** | `skills/deploy/targets.md` | local, Docker, Vercel, Netlify, Fly.io, Azure, Cloud Run, AWS S3, Kubernetes, CI |

## Using it

```text
/app-lifecycle:requirements a notes API with tags and search     ← interview, then REQ-001.. with acceptance criteria
/app-lifecycle:design                                            ← architect proposes; you confirm; sections + decisions are recorded
/app-lifecycle:build                                             ← one requirement at a time; code is linked to REQs
/app-lifecycle:test                                              ← a test per criterion (ID in the test name); results recorded
/app-lifecycle:deploy                                            ← readiness gate → confirmation → deploy → smoke check → recorded
/app-lifecycle:status [REQ-002]                                  ← dashboard, or the full trace of one requirement

# Later, in any session:
/app-lifecycle:change notes need a due date and overdue filter   ← impact analysis → update reqs → design → code → tests → deploy
```

You can also just describe what you want ("build me a ...", "add due dates to notes"). The skill descriptions
make Claude pick the right workflow.

Two conventions make traceability automatic:
- **Test names start with the criterion ID**, for example `REQ-002.AC1 returns 404 for an unknown id`.
- **Behaviour changes go through `change`**: requirements first, then everything below them.

For CI, `lifecycle.py status --require-ready` exits with code 2 when the project isn't ready to deploy:

```bash
git clone --depth 1 https://github.com/mishrabp/ai-agent-kits /tmp/ai-agent-kits
python3 /tmp/ai-agent-kits/claude/app-lifecycle-kit/src/lifecycle.py status --require-ready
```

## Installing it

```bash
claude plugin marketplace add mishrabp/ai-agent-kits
claude plugin install app-lifecycle@ai-agent-kits
```

Or turn it on for everyone in a project by committing this to its `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "ai-agent-kits": { "source": { "source": "github", "repo": "mishrabp/ai-agent-kits" } }
  },
  "enabledPlugins": { "app-lifecycle@ai-agent-kits": true }
}
```

## Develop and release

```bash
python3 -m unittest discover -s tests   # 8 unit tests of the state engine
python3 scripts/smoke_test.py           # MCP server and hook smoke tests
                                        # (or with uv: uv run -m unittest discover -s tests; uv run scripts/smoke_test.py)
claude plugin validate .
claude --plugin-dir .                   # try it in a real session
```

There is no build step and no `pip install`: the server and the hooks use only the Python standard library
(`src/mcp_stdio.py` implements the small part of MCP the server needs). That's deliberate, because Claude Code
installs plugins without running any install step, so nothing could install dependencies on the user's machine.

To release, run the tests and `claude plugin validate .`, then push to `main`. `plugin.json` has no `version`, so
Claude Code versions the plugin by git commit and users get it with `claude plugin update app-lifecycle@ai-agent-kits`.
