# gh-pr-kit

A Claude Code plugin for working with GitHub pull requests. All the code is Python (standard library only).
It's shared through the [ai-agent-kits](https://github.com/mishrabp/ai-agent-kits) marketplace. It contains all four kinds of Claude Code extension:

| Piece | File | What it does |
|---|---|---|
| **Connector** (MCP server) | `server/github_mcp.py` (protocol helper: `server/mcp_stdio.py`), wired up in `.mcp.json` | Six GitHub tools: `list_pull_requests`, `get_pull_request`, `get_pull_request_diff`, `get_latest_release`, `list_merged_pull_requests`, `post_pr_review` |
| **Agent** (subagent) | `agents/pr-reviewer.md` | Read-only reviewer with its own context window. It reads the diff and returns a table of findings. It can't post to GitHub. |
| **Skill** | `skills/pr-review/SKILL.md` | `/gh-pr-kit:pr-review <PR>`: works out the repo and PR, delegates to `pr-reviewer`, shows the findings, and posts them only after you say yes |
| **Skill** | `skills/release-notes/SKILL.md` | `/gh-pr-kit:release-notes [version] [owner/repo]`: groups the PRs merged since the last release into release notes |
| **Plugin** | `.claude-plugin/plugin.json` | Bundles the pieces above, adds a `github_token` setting, and namespaces everything as `gh-pr-kit` |

```
/gh-pr-kit:pr-review 123
        │  skill (main conversation)
        ▼
gh-pr-kit:pr-reviewer          ← subagent, separate context, read-only tools
        │  mcp__plugin_gh-pr-kit_github__get_pull_request / get_pull_request_diff
        ▼
github MCP server (stdio)      ← connector, Python script (standard library only)
        │  GitHub REST API
        ▼
findings → shown to you → "Post this review?" → post_pr_review (only if you say yes)
```

## Authentication

The connector looks for a token in this order:

1. The plugin's `github_token` setting. Claude Code asks for it when you enable the plugin and keeps it in your
   system's credential store.
2. The `GITHUB_TOKEN` or `GH_TOKEN` environment variable.
3. `gh auth token`, if you're logged in with the GitHub CLI.

Reading needs repo read access. Posting reviews also needs pull request write access.

## Install and use it

You need **`python3` 3.9 or newer** on your `PATH`. There is nothing else to install: the code uses only the
Python standard library.

### Claude Code in VS Code

1. Open the Claude Code panel and type `/plugins`.
2. On the **Marketplaces** tab, add `mishrabp/ai-agent-kits`.
3. On the **Plugins** tab, find **gh-pr-kit** and click **Install**, then pick a scope (just you, or this project). Fill in the optional GitHub token when the form asks; leave it empty to use your `gh auth login` session.

Or paste this link into your browser to jump straight to the install dialog:

```text
vscode://anthropic.claude-code/install-plugin?plugin=gh-pr-kit&marketplace=mishrabp/ai-agent-kits
```

Then type `/gh-pr-kit:pr-review cli/cli#14763` in the panel, or just ask, for example "review PR 42". The VS Code extension, the CLI
and the Desktop app share their plugins, so installing in one makes it available in the others.

### Claude Code CLI

```bash
claude plugin marketplace add mishrabp/ai-agent-kits
claude plugin install gh-pr-kit@ai-agent-kits
claude plugin update gh-pr-kit@ai-agent-kits      # later, to get new versions
```

### Claude Desktop

In the **Code** tab, start a **Local** session, click **+** next to the prompt box and choose **Add plugins** (or
**Plugins → Browse plugins**), then install **gh-pr-kit**. If the `ai-agent-kits` marketplace isn't listed yet, run
the two CLI commands above once; the Desktop app reads the same settings as the CLI.

**Cloud** sessions in the Desktop app work like claude.ai/code; see the next section.

### Claude cloud sessions (claude.ai/code, Desktop **Cloud**, mobile)

Cloud sessions run on a fresh VM, and they don't install plugins from marketplaces or from a repository's
`.claude/settings.json`. Load the kit from a clone instead, in your cloud **environment's** settings:

1. **Setup script**: `git clone --depth 1 https://github.com/mishrabp/ai-agent-kits /opt/ai-agent-kits`
2. **Environment variable**: `CLAUDE_CODE_PLUGIN_DIRS=/opt/ai-agent-kits/claude/gh-pr-kit`
   (to load several kits, separate the paths with `:`)

Every cloud session that uses that environment then has the kit, with the same commands as locally.

For private repositories or more than 60 requests an hour, also add an environment variable `GH_TOKEN` with a
fine-grained, read-only GitHub token. Use `GH_TOKEN`, not `GITHUB_TOKEN`: the plugin's `.mcp.json` sets
`GITHUB_TOKEN` from its own `github_token` setting, which can't be filled in on a cloud VM. Everyone who uses the
environment can read its variables, so don't use a token with write access there.

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
  "enabledPlugins": { "gh-pr-kit@ai-agent-kits": true }
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

KIT = Path("/path/to/ai-agent-kits/claude/gh-pr-kit")

async def main():
    options = ClaudeAgentOptions(
        plugins=[{"type": "local", "path": str(KIT)}],
        setting_sources=[],  # load only this kit, not the plugins and settings on this machine
        allowed_tools=["mcp__plugin_gh-pr-kit_github__get_pull_request",
                      "mcp__plugin_gh-pr-kit_github__get_pull_request_diff",
                      "mcp__plugin_gh-pr-kit_github__list_pull_requests",
                      "Agent"],
    )
    async for message in query(prompt="/gh-pr-kit:pr-review cli/cli#14763", options=options):
        if isinstance(message, ResultMessage):
            print(message.result)

asyncio.run(main())
```

**Only the MCP server, with any MCP client.** `server/github_mcp.py` is a standard stdio MCP server, so any app or agent
that speaks MCP can start it. Most clients take the same `command`/`args` shape: Claude Desktop's
`claude_desktop_config.json`, Gemini CLI's `settings.json` and Cursor's `mcp.json` use `mcpServers`, as below;
VS Code's `.vscode/mcp.json` (GitHub Copilot) uses a `servers` key with `"type": "stdio"` instead.

```json
{
  "mcpServers": {
    "github": {
      "command": "python3",
      "args": ["/path/to/ai-agent-kits/claude/gh-pr-kit/server/github_mcp.py"],
      "env": { "GH_TOKEN": "ghp_..." }
    }
  }
}
```

With the Agent SDK, pass the same server in code (`KIT` as in the example above):

```python
options = ClaudeAgentOptions(
    setting_sources=[],
    mcp_servers={
        "github": {
            "command": "python3",
            "args": [str(KIT / "server/github_mcp.py")],
            "env": {"GH_TOKEN": "ghp_..."},  # a GitHub token (optional for public repos)
        }
    },
    allowed_tools=["mcp__github__get_pull_request"],
)
# then: query(prompt="Summarize pull request cli/cli#14763.", options=options)
```

From plain Python with the official MCP client (`pip install mcp`), for frameworks that aren't MCP hosts:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python3", args=["/path/to/ai-agent-kits/claude/gh-pr-kit/server/github_mcp.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()  # hand these to your LLM as tool definitions
            print([t.name for t in tools.tools])
            # when the LLM picks a tool: await session.call_tool(name, arguments)

asyncio.run(main())
```

**Only the skills.** The skills in `skills/` are plain `SKILL.md` files (the Agent Skills format), but they are written for this
plugin: their `allowed-tools` and the `pr-reviewer` agent's `tools` use the plugin's tool names
(`mcp__plugin_gh-pr-kit_github__…`). If you copy them into another agent with the MCP server registered under a
different name, update those names to match (for a server named `github`: `mcp__github__get_pull_request`, and so on).

## Commands

```text
/gh-pr-kit:pr-review 123                       # PR in the current repo (taken from the git remote)
/gh-pr-kit:pr-review cli/cli#14763             # any repo
/gh-pr-kit:pr-review https://github.com/o/r/pull/9
/gh-pr-kit:release-notes 2.4.0
@agent-gh-pr-kit:pr-reviewer review o/r#9     # call the subagent directly
```

You can also just ask, for example "review PR 42" or "draft release notes for 2.4.0". Claude loads the right skill from its description.

## Develop

```bash
python3 scripts/smoke_test.py     # runs the MCP server against real GitHub (read-only tools)
                                  # optional: python3 scripts/smoke_test.py owner/repo 123
                                  # or with uv: uv run scripts/smoke_test.py
claude plugin validate .
claude --plugin-dir .             # try the plugin in a real session without installing it
                                  # (run /reload-plugins after edits)
```

There is no build step and no install step. The server uses only the Python standard library, and
`server/mcp_stdio.py` implements the small part of MCP it needs (initialize, tools/list, tools/call, argument
checks). This matters because Claude Code installs plugins **without running any install step**, so a
`pip install mcp` would never happen on the user's machine. A stdlib-only script always starts.

## Release

Push to `main`. `plugin.json` has no `version`, so Claude Code versions the plugin by git commit, and users pick up
the change with `claude plugin update gh-pr-kit@ai-agent-kits`. Run the smoke test and `claude plugin validate .`
before you push.

## Lessons learned while building it

- **Avoid `` !`command` `` in skills that other people will install.** That shell command runs before Claude
  reads the skill, and it needs Bash permission. Where that permission hasn't been granted, the whole skill
  quietly aborts. These skills tell Claude to run `git remote get-url origin` instead, and pre-approve only that
  command with `allowed-tools: Bash(git remote get-url:*)`.
- **Tool names for plugin MCP servers** are `mcp__plugin_<plugin>_<server>__<tool>`, here
  `mcp__plugin_gh-pr-kit_github__get_pull_request`. Use those names in the agent's `tools` and the skills'
  `allowed-tools`.
- **A plugin's name can't start with `claude-`**, because that prefix is reserved.
- **Write actions** (`post_pr_review`) are left out of every `allowed-tools` list on purpose, so Claude Code
  always asks before posting anything publicly.
