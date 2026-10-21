#!/usr/bin/env python3
# Runs the CLI the way Claude Code does: as an MCP server over stdio, and as the two hooks.
import json
import os
import subprocess
import sys
import tempfile

BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "lifecycle.py")
project = tempfile.mkdtemp(prefix="lifecycle-smoke-")
failed = 0


def check(label, cond, extra=""):
    global failed
    print(f"{'PASS' if cond else 'FAIL'}  {label}" + (f"  ({extra})" if extra else ""))
    if not cond:
        failed += 1


proc = subprocess.Popen(
    [sys.executable, BIN, "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
    env={**os.environ, "LIFECYCLE_PROJECT_DIR": project},
)
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


def call_raw(name, args=None):
    return request("tools/call", {"name": name, "arguments": args or {}})


def call(name, args=None):
    res = call_raw(name, args)
    text = res["content"][0]["text"]
    if res.get("isError"):
        raise RuntimeError(f"{name}: {text}")
    return json.loads(text)


try:
    request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1.0.0"}})
    tools = request("tools/list")["tools"]
    check("tools/list", len(tools) == 16, ", ".join(t["name"] for t in tools))
    check("status before init", call("status")["initialized"] is False)
    call("init_project", {"name": "Smoke App", "summary": "Smoke test", "kind": "api"})
    up = call("upsert_requirement", {"title": "Health check", "acceptance_criteria": ["GET /health returns 200"], "status": "approved"})
    check("upsert_requirement returns next steps",
          up["result"]["id"] == "REQ-001" and any("Design" in n for n in up["next_steps"]), up["next_steps"][0])
    bad = call_raw("link_code", {"requirement_ids": ["REQ-404"], "files": ["a.js"]})
    check("invalid input is a tool error, not a crash", bad.get("isError") is True, bad["content"][0]["text"])
    bad = call_raw("record_deployment", {"environment": "prod", "status": "shipped"})
    check("schema violations are tool errors", bad.get("isError") is True, bad["content"][0]["text"])
finally:
    proc.stdin.close()
    proc.wait(timeout=10)

hook_env = {**os.environ, "CLAUDE_PROJECT_DIR": project}
out = subprocess.run([sys.executable, BIN, "session-start"], env=hook_env, capture_output=True, text=True, check=True).stdout
ctx = json.loads(out).get("hookSpecificOutput", {}).get("additionalContext", "")
check("session-start hook injects status", "Project: Smoke App" in ctx and "Next steps" in ctx)

subprocess.run(
    [sys.executable, BIN, "track-edit"], env=hook_env, check=True, text=True,
    input=json.dumps({"tool_name": "Write", "tool_input": {"file_path": os.path.join(project, "src/server.js")}, "cwd": project}),
)
with open(os.path.join(project, ".lifecycle/state.json"), encoding="utf-8") as f:
    state = json.load(f)
check("track-edit hook records changed file", "src/server.js" in state["code"]["changed_files"])

silent = subprocess.run([sys.executable, BIN, "session-start"], env={**os.environ, "CLAUDE_PROJECT_DIR": tempfile.gettempdir()},
                        capture_output=True, text=True, check=True).stdout
check("hooks are silent outside lifecycle projects", silent == "")

print(f"\n{failed} check(s) failed" if failed else "\nAll smoke checks passed")
sys.exit(1 if failed else 0)
