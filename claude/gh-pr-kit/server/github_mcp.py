#!/usr/bin/env python3
# GitHub connector for the gh-pr-kit plugin: a small MCP server (stdio) over the GitHub REST API.
# Auth: GITHUB_TOKEN, else GH_TOKEN, else the token of a logged-in `gh` CLI.
# Standard library only: Claude Code installs plugins without running any install step.
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from mcp_stdio import Server

API = os.environ.get("GITHUB_API_URL") or "https://api.github.com"
VERSION = "1.0.0"


def resolve_token():
    for v in (os.environ.get("GITHUB_TOKEN"), os.environ.get("GH_TOKEN")):
        # An unset plugin userConfig value can arrive as the literal "${user_config.x}" text.
        if v and not v.startswith("${"):
            return v.strip()
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout
        return out.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


token = resolve_token()


def gh(path, method="GET", body=None, accept="application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "User-Agent": f"gh-pr-kit/{VERSION}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            text = res.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"GitHub {method} {path} failed: {err.code} {err.reason} {detail}") from None
    return text if "diff" in accept else json.loads(text)


def login(obj):
    return (obj.get("user") or {}).get("login")


def label_names(obj):
    return [l["name"] for l in obj.get("labels") or []]


def string(description=None, **extra):
    return {"type": "string", **({"description": description} if description else {}), **extra}


def integer(description=None, **extra):
    return {"type": "integer", **({"description": description} if description else {}), **extra}


REPO_ARGS = {
    "owner": string("Repository owner (user or org), e.g. 'cli'"),
    "repo": string("Repository name, e.g. 'cli'"),
}
PR_ARGS = {**REPO_ARGS, "number": integer("Pull request number", minimum=1)}
READ_ONLY = {"readOnlyHint": True, "openWorldHint": True}

server = Server("gh-pr-kit-github", VERSION)


@server.tool(
    "list_pull_requests",
    "List pull requests in a repository, newest first.",
    {
        **REPO_ARGS,
        "state": string(enum=["open", "closed", "all"], default="open"),
        "limit": integer(minimum=1, maximum=100, default=20),
    },
    required=["owner", "repo"],
    title="List pull requests",
    annotations=READ_ONLY,
)
def list_pull_requests(owner, repo, state, limit):
    prs = gh(f"/repos/{owner}/{repo}/pulls?state={state}&per_page={limit}&sort=created&direction=desc")
    return [
        {
            "number": p["number"],
            "title": p["title"],
            "author": login(p),
            "state": p["state"],
            "draft": p.get("draft"),
            "merged_at": p.get("merged_at"),
            "url": p["html_url"],
        }
        for p in prs
    ]


@server.tool(
    "get_pull_request",
    "Get a pull request's metadata (title, body, author, branches, labels, review state) and its changed files with line counts.",
    PR_ARGS,
    required=["owner", "repo", "number"],
    title="Get pull request",
    annotations=READ_ONLY,
)
def get_pull_request(owner, repo, number):
    pr = gh(f"/repos/{owner}/{repo}/pulls/{number}")
    files = gh(f"/repos/{owner}/{repo}/pulls/{number}/files?per_page=100")
    return {
        "number": pr["number"],
        "title": pr["title"],
        "body": pr.get("body"),
        "author": login(pr),
        "state": pr["state"],
        "draft": pr.get("draft"),
        "merged": pr.get("merged"),
        "base": (pr.get("base") or {}).get("ref"),
        "head": (pr.get("head") or {}).get("ref"),
        "labels": label_names(pr),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "changed_files": pr.get("changed_files"),
        "url": pr["html_url"],
        "files": [
            {"filename": f["filename"], "status": f["status"], "additions": f["additions"], "deletions": f["deletions"]}
            for f in files
        ],
    }


@server.tool(
    "get_pull_request_diff",
    "Get the unified diff of a pull request. Long diffs are truncated to max_chars.",
    {**PR_ARGS, "max_chars": integer(minimum=1000, maximum=400000, default=80000)},
    required=["owner", "repo", "number"],
    title="Get pull request diff",
    annotations=READ_ONLY,
)
def get_pull_request_diff(owner, repo, number, max_chars):
    diff = gh(f"/repos/{owner}/{repo}/pulls/{number}", accept="application/vnd.github.v3.diff")
    if len(diff) > max_chars:
        return f"{diff[:max_chars]}\n\n[diff truncated: showing {max_chars} of {len(diff)} characters]"
    return diff


@server.tool(
    "get_latest_release",
    "Get the most recent published release (tag and date). Falls back to the newest tag when the repo has no releases.",
    REPO_ARGS,
    required=["owner", "repo"],
    title="Get latest release",
    annotations=READ_ONLY,
)
def get_latest_release(owner, repo):
    try:
        r = gh(f"/repos/{owner}/{repo}/releases/latest")
        return {"tag": r["tag_name"], "name": r.get("name"), "published_at": r.get("published_at"), "url": r["html_url"]}
    except RuntimeError:
        tags = gh(f"/repos/{owner}/{repo}/tags?per_page=1")
        if not tags:
            return {"tag": None, "note": "Repository has no releases or tags"}
        commit = gh(f"/repos/{owner}/{repo}/commits/{tags[0]['commit']['sha']}")
        return {
            "tag": tags[0]["name"],
            "published_at": commit["commit"]["committer"]["date"],
            "note": "From newest tag (no releases)",
        }


@server.tool(
    "list_merged_pull_requests",
    "List pull requests merged into the repository after a date (ISO 8601), for changelogs and release notes.",
    {
        **REPO_ARGS,
        "since": string("ISO 8601 date-time, e.g. 2026-09-01T00:00:00Z"),
        "base": string("Only PRs merged into this branch"),
        "limit": integer(minimum=1, maximum=100, default=100),
    },
    required=["owner", "repo", "since"],
    title="List merged pull requests",
    annotations=READ_ONLY,
)
def list_merged_pull_requests(owner, repo, since, limit, base=None):
    q = " ".join(
        x for x in [f"repo:{owner}/{repo}", "is:pr", "is:merged", f"merged:>{since}", f"base:{base}" if base else ""] if x
    )
    res = gh(f"/search/issues?q={urllib.parse.quote(q, safe='')}&sort=updated&order=desc&per_page={limit}")
    return {
        "total": res["total_count"],
        "pull_requests": [
            {
                "number": i["number"],
                "title": i["title"],
                "author": login(i),
                "labels": label_names(i),
                "merged_at": (i.get("pull_request") or {}).get("merged_at"),
                "url": i["html_url"],
            }
            for i in res["items"]
        ],
    }


@server.tool(
    "post_pr_review",
    "Publish a review on a pull request. This is visible to everyone on the PR: only call it after the user has approved the exact text.",
    {
        **PR_ARGS,
        "body": string("Review text (Markdown)", minLength=1),
        "event": string(enum=["COMMENT", "APPROVE", "REQUEST_CHANGES"], default="COMMENT"),
    },
    required=["owner", "repo", "number", "body"],
    title="Post pull request review",
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
)
def post_pr_review(owner, repo, number, body, event):
    r = gh(f"/repos/{owner}/{repo}/pulls/{number}/reviews", method="POST", body={"body": body, "event": event})
    return {"id": r["id"], "state": r["state"], "url": r["html_url"]}


if __name__ == "__main__":
    if not token:
        print("gh-pr-kit: no GitHub token found; only public data will be readable (60 requests/hour).", file=sys.stderr)
    server.run()
