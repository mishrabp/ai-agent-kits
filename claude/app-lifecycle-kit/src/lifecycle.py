#!/usr/bin/env python3
# Entry point for the MCP server and the hooks (standard library only, no install step).
#   lifecycle mcp            run the MCP server on stdio (used by .mcp.json)
#   lifecycle session-start  SessionStart hook: add the project status to Claude's context
#   lifecycle track-edit     PostToolUse hook: remember files changed since the last green test run
#   lifecycle status         print the dashboard as JSON (for humans and CI)
import json
import os
import sys

import state as st


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "mcp"
    root = st.project_dir()

    if cmd == "mcp":
        from server import run_mcp

        run_mcp()
        return 0

    if cmd == "session-start":
        s = st.load(root)
        if not s:
            return 0  # Not a lifecycle project: stay silent.
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": st.brief(s)}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0

    if cmd == "track-edit":
        # Hooks must never break the session: swallow every error.
        try:
            data = "" if sys.stdin.isatty() else sys.stdin.buffer.read().decode("utf-8")
            hook_input = json.loads(data or "{}")
            tool_input = hook_input.get("tool_input") or {}
            file = tool_input.get("file_path") or tool_input.get("notebook_path")
            cwd = hook_input.get("cwd")
            st.track_edit(cwd if cwd and not os.environ.get("CLAUDE_PROJECT_DIR") else root, file)
        except Exception:  # noqa: BLE001
            pass
        return 0

    if cmd == "status":
        s = st.load(root)
        if not s:
            print(f"No lifecycle project in {root}")
            return 1
        a = st.analyze(s)
        print(json.dumps({
            "project": a["project"]["name"], "counts": a["counts"], "deploy_ready": a["deploy_ready"],
            "blockers": a["deploy_blockers"], "next_steps": a["next_steps"],
        }, indent=2, ensure_ascii=False))
        return 2 if "--require-ready" in sys.argv and not a["deploy_ready"] else 0

    print(f'Unknown command "{cmd}". Use: mcp | session-start | track-edit | status [--require-ready]', file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
