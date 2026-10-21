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

## Install and use it

You need **`python3` 3.9 or newer** on your `PATH`. There is nothing else to install: the code uses only the
Python standard library.

### Claude Code in VS Code

1. Open the Claude Code panel and type `/plugins`.
2. On the **Marketplaces** tab, add `mishrabp/ai-agent-kits`.
3. On the **Plugins** tab, find **app-lifecycle** and click **Install**, then pick a scope (just you, or this project).

Or paste this link into your browser to jump straight to the install dialog:

```text
vscode://anthropic.claude-code/install-plugin?plugin=app-lifecycle&marketplace=mishrabp/ai-agent-kits
```

Then type `/app-lifecycle:requirements a notes API with tags` in the panel, or just ask, for example "build me a notes API". The VS Code extension and the
Claude Code CLI on the same machine share their plugins, so installing in one makes it available in the other.

### Claude Code CLI

```bash
claude plugin marketplace add mishrabp/ai-agent-kits
claude plugin install app-lifecycle@ai-agent-kits
claude plugin update app-lifecycle@ai-agent-kits      # later, to get new versions
```

### Claude Desktop

The Desktop app has its own plugin manager, so you don't need the terminal.

Install it by uploading a zip:

1. Download the repository (**Code › Download ZIP** on GitHub) and unzip it.
2. Zip the `claude/app-lifecycle-kit` folder by itself, so the archive holds `app-lifecycle-kit/.claude-plugin/plugin.json`.
   On Windows: right-click the folder › **Send to** › **Compressed (zipped) folder**.
3. Click **Customize** in the sidebar, then **Plugins › ＋ Add › Upload plugin**, and select the zip.
   **app-lifecycle** then appears under **Yours**.

An uploaded copy doesn't update by itself: to get a newer version, upload a new zip.

The install is saved to your claude.ai account, not to one machine. Each part of the Desktop app loads a different
part of a plugin:

| | Works? |
|---|---|
| **Code** tab | Yes, everything, and this is where it's meant to run: open your project folder, then `/app-lifecycle:requirements ...`. If it doesn't show up in a Code session, install it there with **+ › Add plugins** |
| **Cowork** | Mostly: skills, agents, hooks and the lifecycle connector load, but it keeps its state in the folder the session works in, so point Cowork at your project folder |
| **Chat** | No: chat ignores the connector, agents and hooks the workflow depends on |

Things to know:

- **Python on Windows.** The kit's MCP server starts with `python3`. On Windows that command often doesn't exist or opens
  the Microsoft Store. Install Python from the Microsoft Store (it provides `python3`), then check that `python3 --version`
  works in a new terminal before you start a session.
- **WSL.** The Desktop app doesn't load plugins in WSL sessions. A kit you installed with the CLI inside WSL stays in WSL's
  `~/.claude` and doesn't appear in the Windows app; install it through **Customize** instead.
- **Cloud** sessions in the Desktop app work like claude.ai/code; see the next section.

### Claude cloud sessions (claude.ai/code, Desktop **Cloud**, mobile)

Cloud sessions run on a fresh VM, and they don't install plugins from marketplaces or from a repository's
`.claude/settings.json`. Load the kit from a clone instead, in your cloud **environment's** settings:

1. **Setup script**: `git clone --depth 1 https://github.com/mishrabp/ai-agent-kits /opt/ai-agent-kits`
2. **Environment variable**: `CLAUDE_CODE_PLUGIN_DIRS=/opt/ai-agent-kits/claude/app-lifecycle-kit`
   (to load several kits, separate the paths with `:`)

Every cloud session that uses that environment then has the kit, with the same commands as locally.

The hooks and the `.lifecycle/` state work the same as locally: commit `.lifecycle/` in the repository so the next
cloud session picks up where the last one stopped.

> This recipe follows the Claude Code docs (setup scripts and `CLAUDE_CODE_PLUGIN_DIRS`), and the variable was tested
> locally, but it hasn't been run in a cloud session yet. If a setup result is cached and you need a newer version of
> the kit, run `git -C /opt/ai-agent-kits pull` in the session.

### Turn it on for everyone in a project

Commit this to the project's `.claude/settings.json`. Teammates get the plugin after they trust the folder:

```json
{
  "extraKnownMarketplaces": {
    "ai-agent-kits": { "source": { "source": "github", "repo": "mishrabp/ai-agent-kits" } }
  },
  "enabledPlugins": { "app-lifecycle@ai-agent-kits": true }
}
```

### In your own agentic AI application

Clone the repository first: `git clone https://github.com/mishrabp/ai-agent-kits`.

**The whole kit, with the Claude Agent SDK.** The SDK loads a plugin folder directly: its skills, agents, hooks and
MCP server all work, under the same names as in Claude Code (`pip install claude-agent-sdk`):

```python
import asyncio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

KIT = Path("/path/to/ai-agent-kits/claude/app-lifecycle-kit")

async def main():
    options = ClaudeAgentOptions(
        plugins=[{"type": "local", "path": str(KIT)}],
        setting_sources=[],  # load only this kit, not the plugins and settings on this machine
        cwd="/path/to/your/project",  # the project the agent works on
        allowed_tools=["mcp__plugin_app-lifecycle_lifecycle__*",
                      "Agent",
                      "Read",
                      "Edit",
                      "Write",
                      "Bash"],
    )
    async for message in query(prompt="/app-lifecycle:status", options=options):
        if isinstance(message, ResultMessage):
            print(message.result)

asyncio.run(main())
```

**Only the MCP server, with any MCP client.** `src/lifecycle.py` is a standard stdio MCP server, so any app or agent
that speaks MCP can start it. Most clients take the same `command`/`args` shape: Claude Desktop's
`claude_desktop_config.json`, Gemini CLI's `settings.json` and Cursor's `mcp.json` use `mcpServers`, as below;
VS Code's `.vscode/mcp.json` (GitHub Copilot) uses a `servers` key with `"type": "stdio"` instead.

```json
{
  "mcpServers": {
    "lifecycle": {
      "command": "python3",
      "args": ["/path/to/ai-agent-kits/claude/app-lifecycle-kit/src/lifecycle.py", "mcp"],
      "env": { "LIFECYCLE_PROJECT_DIR": "/path/to/your/project" }
    }
  }
}
```

With the Agent SDK, pass the same server in code (`KIT` as in the example above):

```python
options = ClaudeAgentOptions(
    setting_sources=[],
        cwd="/path/to/your/project",
    mcp_servers={
        "lifecycle": {
            "command": "python3",
            "args": [str(KIT / "src/lifecycle.py"), "mcp"],
            "env": {"LIFECYCLE_PROJECT_DIR": "/path/to/your/project"},  # the project whose `.lifecycle/` state the server manages
        }
    },
    allowed_tools=["mcp__lifecycle__*"],
)
# then: query(prompt="Show the lifecycle status of this project.", options=options)
```

From plain Python with the official MCP client (`pip install mcp`), for frameworks that aren't MCP hosts:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python3", args=["/path/to/ai-agent-kits/claude/app-lifecycle-kit/src/lifecycle.py", "mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()  # hand these to your LLM as tool definitions
            print([t.name for t in tools.tools])
            # when the LLM picks a tool: await session.call_tool(name, arguments)

asyncio.run(main())
```

**Only the skills.** The skills in `skills/` are plain `SKILL.md` files (the Agent Skills format), but they are written for this
plugin: they call the lifecycle MCP tools and the `architect`, `test-engineer` and `impact-analyst` agents, and they
rely on the two hooks in `hooks/hooks.json` to keep the state current. Use the whole kit (the Agent SDK route above)
rather than the skills on their own.

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

To release, run the tests and `claude plugin validate .`, raise `version` in `.claude-plugin/plugin.json` (and in `pyproject.toml`), then push to `main`.
Users get the new version with `claude plugin update app-lifecycle@ai-agent-kits`; a push that doesn't change `version`
doesn't reach them. Directory listings update after the new version passes review.
