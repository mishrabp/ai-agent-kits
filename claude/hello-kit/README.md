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
# 1. Talk to the connector yourself, the way Claude Code does:
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_fortune","arguments":{"name":"Ada"}}}' \
  | python3 server/fortune_server.py

# 2. Load the whole plugin for one session (CLI or the VS Code terminal):
claude --plugin-dir ./hello-kit
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

## Share it through GitHub

The repo's root `.claude-plugin/marketplace.json` lists this folder (`./claude/hello-kit`), so the GitHub repo
itself is the marketplace. Anyone can install it with:

```bash
claude plugin marketplace add mishrabp/ai-agent-kits
claude plugin install hello-kit@ai-agent-kits
```

You need `python3` (3.9+) on your `PATH` for the connector. To turn it on for everyone in a project, commit this
to the project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "ai-agent-kits": { "source": { "source": "github", "repo": "mishrabp/ai-agent-kits" } }
  },
  "enabledPlugins": { "hello-kit@ai-agent-kits": true }
}
```

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
