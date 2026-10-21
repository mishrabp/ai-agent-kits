#!/usr/bin/env python3
# Starts the MCP server the way Claude Code does (stdio), lists its tools,
# and calls the read-only ones against a public repository.
# Usage: python3 scripts/smoke_test.py [owner/repo] [pr-number]
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server", "github_mcp.py")

slug = sys.argv[1] if len(sys.argv) > 1 else "cli/cli"
pr_arg = sys.argv[2] if len(sys.argv) > 2 else None
owner, repo = slug.split("/")

proc = subprocess.Popen([sys.executable, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
next_id = 0


def request(method, params=None):
    global next_id
    next_id += 1
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": next_id, "method": method, "params": params or {}}) + "\n")
    proc.stdin.flush()
    reply = json.loads(proc.stdout.readline())
    if "error" in reply:
        raise RuntimeError(f"{method}: {reply['error']['message']}")
    return reply["result"]


failed = 0


def check(label, cond, extra=""):
    global failed
    print(f"{'PASS' if cond else 'FAIL'}  {label}" + (f"  ({extra})" if extra else ""))
    if not cond:
        failed += 1


def call(name, args):
    res = request("tools/call", {"name": name, "arguments": args})
    text = res["content"][0]["text"] if res.get("content") else ""
    if res.get("isError"):
        raise RuntimeError(f"{name}: {text}")
    return json.loads(text) if text.startswith(("{", "[")) else text


try:
    request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "gh-pr-kit-smoke-test", "version": "1.0.0"}})
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

    names = sorted(t["name"] for t in request("tools/list")["tools"])
    check("tools/list returns 6 tools", len(names) == 6, ", ".join(names))

    merged = call("list_pull_requests", {"owner": owner, "repo": repo, "state": "closed", "limit": 5})
    check("list_pull_requests", isinstance(merged, list) and len(merged) > 0, f"{len(merged)} PRs")

    # Release-branch merges can have no changed files (and so an empty diff): use the first PR that has some.
    for candidate in [int(pr_arg)] if pr_arg else [p["number"] for p in merged]:
        number = candidate
        pr = call("get_pull_request", {"owner": owner, "repo": repo, "number": number})
        if pr["files"]:
            break
    check("get_pull_request", pr["number"] == number, f"#{pr['number']} \"{pr['title']}\", {len(pr['files'])} files")

    diff = call("get_pull_request_diff", {"owner": owner, "repo": repo, "number": number, "max_chars": 5000})
    check("get_pull_request_diff", isinstance(diff, str) and diff.startswith("diff --git"), f"{len(diff)} chars")

    rel = call("get_latest_release", {"owner": owner, "repo": repo})
    check("get_latest_release", bool(rel["tag"]), f"{rel['tag']} @ {rel['published_at']}")

    since = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    m = call("list_merged_pull_requests", {"owner": owner, "repo": repo, "since": since, "limit": 10})
    check("list_merged_pull_requests", isinstance(m["total"], int), f"{m['total']} merged in the last 14 days")

    bad = request("tools/call", {"name": "get_pull_request", "arguments": {"owner": owner, "repo": repo, "number": 0}})
    check("invalid arguments are a tool error, not a crash", bad.get("isError") is True, bad["content"][0]["text"])
except Exception as err:  # noqa: BLE001
    check("tool call", False, str(err))
finally:
    proc.stdin.close()
    proc.wait(timeout=10)

print(f"\n{failed} check(s) failed" if failed else "\nAll checks passed (post_pr_review is write-only and not called).")
sys.exit(1 if failed else 0)
