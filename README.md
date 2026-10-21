# ai-agent-kits

Plugins for AI coding agents, starting with **Claude Code**. Support for GitHub Copilot and Gemini is planned
in this same repo.

| Kit | Agent | What it does |
|---|---|---|
| [hello-kit](claude/hello-kit) | Claude Code | The smallest complete plugin: one skill, one subagent and one connector (MCP server). Start here to learn how plugins work. |
| [gh-pr-kit](claude/gh-pr-kit) | Claude Code | Review GitHub pull requests and draft release notes. |
| [app-lifecycle](claude/app-lifecycle-kit) | Claude Code | Requirements → design → build → test → deploy, with persistent, traceable state. |

All the code is Python, standard library only, so there is nothing to `pip install`. You need **`python3` 3.9
or newer** on your `PATH`.

## Install in Claude Code

This repo is a Claude Code plugin marketplace. Add it once, then install the kits you want:

```bash
claude plugin marketplace add mishrabp/ai-agent-kits
claude plugin install hello-kit@ai-agent-kits
claude plugin install gh-pr-kit@ai-agent-kits
claude plugin install app-lifecycle@ai-agent-kits
```

You can also do this inside a session with `/plugin`. The Claude Code CLI, the VS Code extension and the Desktop
app share the same plugins, so installing once covers all three. Then try `/hello-kit:hello Ada`.

To get updates:

```bash
claude plugin marketplace update ai-agent-kits
claude plugin update hello-kit@ai-agent-kits
```

### Turn kits on for everyone in a project

Commit this to the project's `.claude/settings.json`. Teammates get the marketplace and the plugins after they
trust the folder:

```json
{
  "extraKnownMarketplaces": {
    "ai-agent-kits": { "source": { "source": "github", "repo": "mishrabp/ai-agent-kits" } }
  },
  "enabledPlugins": {
    "gh-pr-kit@ai-agent-kits": true,
    "app-lifecycle@ai-agent-kits": true
  }
}
```

### Claude Code cloud sessions (claude.ai/code)

Cloud sessions don't install plugins from marketplaces, including the ones a repo's `.claude/settings.json`
declares. Load the kits from a clone instead, in your cloud environment's settings:

1. **Setup script**: `git clone --depth 1 https://github.com/mishrabp/ai-agent-kits /opt/ai-agent-kits`
2. **Environment variable**: `CLAUDE_CODE_PLUGIN_DIRS=/opt/ai-agent-kits/claude/hello-kit:/opt/ai-agent-kits/claude/gh-pr-kit`

Each kit's README has the details, plus how to use the kit from VS Code, the Desktop app, and your own agentic
AI application (Claude Agent SDK, or any MCP client).

## Repository layout

```
ai-agent-kits/
├── .claude-plugin/marketplace.json   the Claude Code marketplace: lists the kits under claude/
├── claude/                           Claude Code plugins
│   ├── hello-kit/
│   ├── gh-pr-kit/
│   └── app-lifecycle-kit/
└── _doc/                             reference material
```

Each kit's README explains how it works and how to run its tests.

## License

[MIT](LICENSE)
