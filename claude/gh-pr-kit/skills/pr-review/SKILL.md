---
name: pr-review
description: Reviews a GitHub pull request and optionally posts the review to GitHub. Use when the user asks to review, check or look over a PR, gives a PR number or a github.com/.../pull/N URL, or asks "is this PR safe to merge".
argument-hint: "<pr-number | owner/repo#number | PR URL>"
allowed-tools: Bash(git remote get-url:*) mcp__plugin_gh-pr-kit_github__get_pull_request mcp__plugin_gh-pr-kit_github__list_pull_requests
---

# Review a GitHub pull request

## Input
Requested PR: $ARGUMENTS

## Steps

1. **Work out the repository and PR number.**
   - `https://github.com/OWNER/REPO/pull/N` or `OWNER/REPO#N`: use those values.
   - A bare number: run `git remote get-url origin` and take OWNER/REPO from it
     (`git@github.com:OWNER/REPO.git` or `https://github.com/OWNER/REPO(.git)`).
   - No PR given: call `list_pull_requests` for the repo, show the open PRs, and ask which one to review.
   - If you still can't tell the repository, ask the user. Don't guess.

2. **Delegate the review** to the `gh-pr-kit:pr-reviewer` subagent with a prompt like:
   "Review pull request OWNER/REPO#N." Its work (reading the full diff) stays out of the main
   conversation; you only get its findings back.

3. **Show the findings** to the user exactly as the subagent returned them, followed by one line with the PR link.

4. **Offer to post.** Ask: "Post this review on the PR as a comment?" Then:
   - If the user says yes, call `post_pr_review` with `event: "COMMENT"` and the findings as the body, ending with the
     line `_Reviewed with Claude Code (gh-pr-kit)_`. Use `REQUEST_CHANGES` or `APPROVE` only if the user asks
     for it by name.
   - Never post without that explicit yes. `post_pr_review` isn't pre-approved in this skill, so Claude Code will
     also ask for permission.
   - Reply with the review URL that the tool returns.
