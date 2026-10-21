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

## Requirements

`python3` (3.9 or newer) on the `PATH`. Nothing else: there is no `pip install` step. `pyproject.toml` records
this (`requires-python`, empty `dependencies`), so `uv run scripts/smoke_test.py` also works.

## Authentication

The connector looks for a token in this order:

1. The plugin's `github_token` setting. Claude Code asks for it when you enable the plugin and keeps it in your
   system's credential store.
2. The `GITHUB_TOKEN` or `GH_TOKEN` environment variable.
3. `gh auth token`, if you're logged in with the GitHub CLI.

Reading needs repo read access. Posting reviews also needs pull request write access.

## Use it

### Install

```bash
claude plugin marketplace add mishrabp/ai-agent-kits
claude plugin install gh-pr-kit@ai-agent-kits
```

This works the same from the CLI, VS Code's terminal and the Desktop app, which share `~/.claude`.

To turn it on for everyone in a project, commit this to the project's `.claude/settings.json`. Teammates get the
plugin after they trust the folder:

```json
{
  "extraKnownMarketplaces": {
    "ai-agent-kits": { "source": { "source": "github", "repo": "mishrabp/ai-agent-kits" } }
  },
  "enabledPlugins": { "gh-pr-kit@ai-agent-kits": true }
}
```

### Only the connector, with any MCP client

The server is a plain Python script, so you can use it without the plugin:

```bash
git clone https://github.com/mishrabp/ai-agent-kits ~/ai-agent-kits
claude mcp add github-prs -- python3 ~/ai-agent-kits/claude/gh-pr-kit/server/github_mcp.py
```

### Commands, once installed

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
