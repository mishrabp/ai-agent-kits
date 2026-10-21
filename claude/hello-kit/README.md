# hello-kit: the four pieces, as small as possible

```
hello-kit/
├── skills/hello/SKILL.md        SKILL      = a recipe          (instructions: "do it like this")
├── agents/poet.md               AGENT      = a helper          (a separate Claude with one job)
├── server/fortune_server.py     CONNECTOR  = a new ability     (a program that gives Claude a tool)
├── .mcp.json                    ...tells Claude Code how to start the connector
├── pyproject.toml               ...Python version and (no) dependencies for the code
└── .claude-plugin/plugin.json   PLUGIN     = the box           (bundles the three above under one name)
```

All the code is Python (standard library only, no `pip install`). The plugin is shared through the
[ai-agent-kits](https://github.com/mishrabp/ai-agent-kits) GitHub repo, which is also a plugin marketplace.

## The one-line versions

| Piece | What it is | What it is NOT |
|---|---|---|
| **Skill** | A Markdown file of **instructions**. Claude reads it and follows it. | It can't do anything new; it only tells Claude how to use what it already has. |
| **Connector** | A **program** that adds a **tool** Claude can call (here `get_fortune`). Also called an MCP server. | It has no instructions and no intelligence; it just answers when called. |
| **Agent** | A **second Claude** with its own instructions, that works in its own separate conversation and hands back only the result. | It isn't a tool and it isn't code: it's another Claude with a focused job. |
| **Plugin** | A **folder** that bundles skills, agents and connectors under one name (`hello-kit`) so they install together. | It does nothing by itself: it's packaging. |

Rule of thumb:
- **"How should it be done?"** → skill
- **"Claude needs to reach something it can't otherwise reach"** → connector
- **"Hand this job to a specialist"** → agent
- **"Share all of it"** → plugin (+ a marketplace on GitHub)

## What actually happens when you type `/hello-kit:hello Ada`

This is the real trace from a test run:

```
You: /hello-kit:hello Ada
 │
 ├─ 1. SKILL loads    skills/hello/SKILL.md is added to the conversation.
 │                    Claude now knows the recipe: fortune → poem → reply.
 │
 ├─ 2. CONNECTOR      Claude calls the tool  get_fortune {"name": "Ada"}
 │                    Claude Code sends that to fortune_server.py, which replies:
 │                    "Fortune for Ada: A pleasant surprise is waiting for you."
 │                    (Claude couldn't have known this fortune without the tool.)
 │
 ├─ 3. AGENT          Claude hands off: Agent(hello-kit:poet, "write a poem about ...")
 │                    The poet is a separate Claude (on the haiku model) that only sees that request.
 │                    It returns just the four lines.
 │
 └─ 4. Reply          👋 Hello, Ada!
                      🥠 A pleasant surprise is waiting for you.
                      📜 Ada, a surprise awaits in store, ...
```

## Read the files (each is tiny)

- **[skills/hello/SKILL.md](skills/hello/SKILL.md):** the header's `description` tells Claude *when* to use it.
  `$ARGUMENTS` becomes `Ada`. The body is plain instructions.
- **[agents/poet.md](agents/poet.md):** the same format as a skill, but the body becomes the *system prompt
  of a separate Claude*. `model: haiku` makes it run on a small, cheap model.
- **[server/fortune_server.py](server/fortune_server.py):** reads one JSON message per line and answers
  `initialize`, `tools/list` and `tools/call`. That's the whole MCP protocol for a tool.
- **[.mcp.json](.mcp.json):** "to start the fortune connector, run `python3 server/fortune_server.py`".
- **[.claude-plugin/plugin.json](.claude-plugin/plugin.json):** just a name and version. Claude Code finds
  `skills/`, `agents/` and `.mcp.json` automatically, by their folder names.

## Try it

```bash
cd claude/hello-kit   # from the repository root

# 1. Talk to the connector yourself, the way Claude Code does:
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_fortune","arguments":{"name":"Ada"}}}' \
  | python3 server/fortune_server.py

# 2. Load the whole plugin for one session (CLI or the VS Code terminal):
claude --plugin-dir .
#    then type:  /hello-kit:hello Ada
#    or just:    say hello to Ada        (Claude picks the skill from its description)
```

Everything gets the plugin's name as a prefix, so nothing clashes with other plugins:
`/hello-kit:hello`, agent `hello-kit:poet`, tool `mcp__plugin_hello-kit_fortune__get_fortune`.

## The same pieces without a plugin

A plugin is optional. Each piece also works on its own in a project's `.claude/` folder; you just can't
version it or share it as one unit:

| Piece | Without a plugin, put it in... | How you use it |
|---|---|---|
| Skill | `.claude/skills/hello/SKILL.md` | `/hello` |
| Agent | `.claude/agents/poet.md` | "ask the poet agent..." or `@agent-poet` |
| Connector | `claude mcp add fortune -- python3 /path/to/fortune_server.py` | Claude calls `get_fortune` when it's useful |

## Install and use it

You need **`python3` 3.9 or newer** on your `PATH`. There is nothing else to install: the code uses only the
Python standard library.

### Claude Code in VS Code

1. Open the Claude Code panel and type `/plugins`.
2. On the **Marketplaces** tab, add `mishrabp/ai-agent-kits`.
3. On the **Plugins** tab, find **hello-kit** and click **Install**, then pick a scope (just you, or this project).

Or paste this link into your browser to jump straight to the install dialog:

```text
vscode://anthropic.claude-code/install-plugin?plugin=hello-kit&marketplace=mishrabp/ai-agent-kits
```

Then type `/hello-kit:hello Ada` in the panel, or just ask, for example "say hello to Ada". The VS Code extension and the
Claude Code CLI on the same machine share their plugins, so installing in one makes it available in the other.

### Claude Code CLI

```bash
claude plugin marketplace add mishrabp/ai-agent-kits
claude plugin install hello-kit@ai-agent-kits
claude plugin update hello-kit@ai-agent-kits      # later, to get new versions
```

### Claude Desktop

The Desktop app has its own plugin manager, so you don't need the terminal.

**From Anthropic's directory.** hello-kit is submitted to Anthropic's plugin directory (listed as **Hello Kit**), which
reviews and security-scans every plugin before listing it. Once it's listed, open **Customize** in the sidebar, then **Plugins ›
Discover**, search for `hello-kit` and click **Install**. Directory plugins update on their own when a new version is
published. The directory is available on Pro, Max, Team and Enterprise plans (on Team and Enterprise, if your
organization keeps it turned on).

**By uploading a zip**, for example while the directory review is still pending:

1. Download the repository (**Code › Download ZIP** on GitHub) and unzip it.
2. Zip the `claude/hello-kit` folder by itself, so the archive holds `hello-kit/.claude-plugin/plugin.json`.
   On Windows: right-click the folder › **Send to** › **Compressed (zipped) folder**.
3. Click **Customize** in the sidebar, then **Plugins › ＋ Add › Upload plugin**, and select the zip.
   **hello-kit** then appears under **Yours**.

An uploaded copy doesn't update by itself: to get a newer version, upload a new zip.

The install is saved to your claude.ai account, not to one machine. Each part of the Desktop app loads a different
part of a plugin:

| | Works? |
|---|---|
| **Code** tab | Yes, everything: `/hello-kit:hello Ada`. If it doesn't show up in a Code session, install it there with **+ › Add plugins** |
| **Cowork** | Yes: the skill, the `poet` agent and the fortune connector all load |
| **Chat** | Partly: only the skill loads. Chat ignores agents and local MCP servers, so Claude makes up the fortune and the poem itself |

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
2. **Environment variable**: `CLAUDE_CODE_PLUGIN_DIRS=/opt/ai-agent-kits/claude/hello-kit`
   (to load several kits, separate the paths with `:`)

Every cloud session that uses that environment then has the kit, with the same commands as locally.

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
  "enabledPlugins": { "hello-kit@ai-agent-kits": true }
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

KIT = Path("/path/to/ai-agent-kits/claude/hello-kit")

async def main():
    options = ClaudeAgentOptions(
        plugins=[{"type": "local", "path": str(KIT)}],
        setting_sources=[],  # load only this kit, not the plugins and settings on this machine
        allowed_tools=["mcp__plugin_hello-kit_fortune__*", "Agent"],
    )
    async for message in query(prompt="/hello-kit:hello Ada", options=options):
        if isinstance(message, ResultMessage):
            print(message.result)

asyncio.run(main())
```

**Only the MCP server, with any MCP client.** `server/fortune_server.py` is a standard stdio MCP server, so any app or agent
that speaks MCP can start it. Most clients take the same `command`/`args` shape: Claude Desktop's
`claude_desktop_config.json`, Gemini CLI's `settings.json` and Cursor's `mcp.json` use `mcpServers`, as below;
VS Code's `.vscode/mcp.json` (GitHub Copilot) uses a `servers` key with `"type": "stdio"` instead.

```json
{
  "mcpServers": {
    "fortune": {
      "command": "python3",
      "args": ["/path/to/ai-agent-kits/claude/hello-kit/server/fortune_server.py"]
    }
  }
}
```

With the Agent SDK, pass the same server in code (`KIT` as in the example above):

```python
options = ClaudeAgentOptions(
    setting_sources=[],
    mcp_servers={
        "fortune": {
            "command": "python3",
            "args": [str(KIT / "server/fortune_server.py")]
        }
    },
    allowed_tools=["mcp__fortune__get_fortune"],
)
# then: query(prompt="Draw a fortune for Ada with the get_fortune tool.", options=options)
```

From plain Python with the official MCP client (`pip install mcp`), for frameworks that aren't MCP hosts:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python3", args=["/path/to/ai-agent-kits/claude/hello-kit/server/fortune_server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()  # hand these to your LLM as tool definitions
            print([t.name for t in tools.tools])
            # when the LLM picks a tool: await session.call_tool(name, arguments)

asyncio.run(main())
```

**Only the skills.** The skill in `skills/hello/` is a plain `SKILL.md` (the Agent Skills format), so you can copy it into any
agent that reads skills: `.claude/skills/hello/` in a project for the Agent SDK or Claude Code, or upload it as a
custom skill on claude.ai. It expects two things to exist where it runs: the `get_fortune` tool (the MCP server
above) and the `poet` subagent (`agents/poet.md`, which goes in `.claude/agents/`). Without them Claude improvises
the fortune and the poem.

## Then look at the bigger kits

| | hello-kit | gh-pr-kit | app-lifecycle-kit |
|---|---|---|---|
| Skills | 1 | 2 | 7 |
| Agents | 1 | 1 | 3 |
| Connector tools | 1 (hand-written) | 6 (GitHub API) | 16 (lifecycle state) |
| Hooks | none | none | 2 (session start, file edits) |
| Build step | none | none | none |

The bigger kits use exactly these four ideas. They just have more of each. They are Python too, standard library
only: instead of one hand-written loop, they share a small helper (`mcp_stdio.py`) that also checks tool
arguments against each tool's schema.
