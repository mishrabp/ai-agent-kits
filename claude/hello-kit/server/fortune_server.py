#!/usr/bin/env python3
# THE CONNECTOR (an MCP server).
# It gives Claude a new ability it doesn't have on its own: drawing a fortune cookie.
#
# An MCP server is just a program that Claude Code starts and talks to over stdin/stdout.
# Each message is one line of JSON. It only has to answer three questions:
#   "initialize"  -> who are you?
#   "tools/list"  -> which tools do you offer?
#   "tools/call"  -> run this tool with these arguments
# (Real servers usually use the `mcp` Python package. This one is written by hand,
#  with only the standard library, so you can see everything that happens.)

import json
import random
import sys

FORTUNES = [
    "A pleasant surprise is waiting for you.",
    "Your code will compile on the first try today.",
    "An old bug will finally reveal itself.",
    "Someone will thank you for your documentation.",
    "Today is a good day to delete code.",
]

# The one tool this server offers.
TOOLS = [
    {
        "name": "get_fortune",
        "description": "Draws a random fortune-cookie message for a person.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Who the fortune is for"}},
            "required": ["name"],
        },
    },
]


def handle(msg):
    method = msg["method"]
    if method == "initialize":
        return {
            "protocolVersion": msg["params"]["protocolVersion"],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fortune", "version": "1.0.0"},
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name, args = msg["params"]["name"], msg["params"]["arguments"]
        if name != "get_fortune":
            raise ValueError(f"Unknown tool {name}")
        fortune = random.choice(FORTUNES)
        return {"content": [{"type": "text", "text": f"Fortune for {args['name']}: {fortune}"}]}
    if method == "ping":
        return {}
    raise ValueError(f"Method not supported: {method}")


for line in sys.stdin:
    if not line.strip():
        continue
    msg = json.loads(line)
    if "id" not in msg:
        continue  # a notification (e.g. "notifications/initialized"): no reply
    try:
        reply = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(msg)}
    except Exception as err:
        reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": str(err)}}
    sys.stdout.write(json.dumps(reply) + "\n")
    sys.stdout.flush()
