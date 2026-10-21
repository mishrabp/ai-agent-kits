---
name: release-notes
description: Drafts release notes or a changelog entry from the GitHub pull requests merged since the last release. Use when the user asks for release notes, a changelog, "what shipped since vX", or a summary of merged PRs.
argument-hint: "[new-version] [owner/repo]"
allowed-tools: Bash(git remote get-url:*) mcp__plugin_gh-pr-kit_github__get_latest_release mcp__plugin_gh-pr-kit_github__list_merged_pull_requests
---

# Draft release notes from merged PRs

## Input
Arguments: $ARGUMENTS

## Steps

1. **Repository.** Use an `owner/repo` in the arguments if there is one; otherwise run
   `git remote get-url origin` and parse it from the URL. If neither works, ask.
2. **New version.** Use a version in the arguments (such as `2.4.0` or `v2.4.0`). If there isn't one, title the notes
   "Unreleased".
3. **Last release.** Call `get_latest_release`. Its `published_at` is the start of the range. If the repo has no
   releases or tags, ask the user for a start date.
4. **Merged PRs.** Call `list_merged_pull_requests` with `since` set to that date. If `total` is more than the number
   returned, say the list is partial.
5. **Group** each PR into exactly one section, using labels first, then the title prefix:
   - **Breaking changes**: label `breaking`, or a `!` after the type (`feat!:`)
   - **Features**: label `feature`/`enhancement`, or a `feat:` prefix
   - **Fixes**: label `bug`, or a `fix:` prefix
   - **Dependencies**: label `dependencies`, or titles starting with `bump`/`chore(deps)`
   - **Other**: everything else (docs, CI, refactors)
   Leave out PRs labelled `skip-changelog`. Drop empty sections.
6. **Write** the notes in this format, rewriting each title as a short, user-facing sentence:

```markdown
## <version> (<today's date, YYYY-MM-DD>)

### Features
- Add dark mode to the settings page (#123, @alice)

### Fixes
- ...

**Full changelog:** https://github.com/OWNER/REPO/compare/<last-tag>...<version>
```

7. Show the draft. Write it to a file (such as `CHANGELOG.md`) or create a GitHub release only if the user asks.
