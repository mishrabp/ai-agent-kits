"""A minimal MCP server over stdio, using only the Python standard library.

Claude Code installs plugins without running any install step, so a connector can't count on
`pip install mcp` having happened. This module covers everything a tools-only server needs:
initialize, tools/list, tools/call and ping, plus JSON Schema checks and defaults for tool arguments.
"""
import copy
import json
import sys

LATEST_PROTOCOL_VERSION = "2025-06-18"


class ArgumentError(ValueError):
    """Tool arguments that don't match the tool's input schema."""


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def to_text(data):
    return data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False)


def text_result(data):
    return {"content": [{"type": "text", "text": to_text(data)}]}


def error_result(message):
    return {"isError": True, "content": [{"type": "text", "text": str(message)}]}


def check(value, schema, where):
    """Validate value against a small JSON Schema subset; returns it with defaults filled in."""
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            raise ArgumentError(f"{where or 'arguments'} must be an object")
        out = {}
        for key, sub in schema.get("properties", {}).items():
            path = f"{where}.{key}" if where else key
            if value.get(key) is not None:
                out[key] = check(value[key], sub, path)
            elif "default" in sub:
                out[key] = copy.deepcopy(sub["default"])
            elif key in schema.get("required", ()):
                raise ArgumentError(f"{path} is required")
        return out  # unknown keys are dropped
    if t == "array":
        if not isinstance(value, list):
            raise ArgumentError(f"{where} must be an array")
        return [check(v, schema.get("items", {}), f"{where}[{i}]") for i, v in enumerate(value)]
    if t == "string":
        if not isinstance(value, str):
            raise ArgumentError(f"{where} must be a string")
        if len(value) < schema.get("minLength", 0):
            raise ArgumentError(f"{where} must have at least {schema['minLength']} character(s)")
    elif t in ("integer", "number"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ArgumentError(f"{where} must be a number")
        if t == "integer":
            if isinstance(value, float) and not value.is_integer():
                raise ArgumentError(f"{where} must be an integer")
            value = int(value)
        if "minimum" in schema and value < schema["minimum"]:
            raise ArgumentError(f"{where} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ArgumentError(f"{where} must be <= {schema['maximum']}")
    elif t == "boolean" and not isinstance(value, bool):
        raise ArgumentError(f"{where} must be true or false")
    if "enum" in schema and value not in schema["enum"]:
        raise ArgumentError(f"{where} must be one of {', '.join(map(str, schema['enum']))} (got {value!r})")
    return value


class Server:
    def __init__(self, name, version):
        self.info = {"name": name, "version": version}
        self.tools = {}

    def tool(self, name, description, properties=None, required=(), title=None, annotations=None):
        """Decorator: registers fn(**arguments) as a tool. Its return value becomes the text result,
        and any exception becomes a tool error instead of crashing the server."""

        def register(fn):
            schema = {"type": "object", "properties": properties or {}, "additionalProperties": False}
            if required:
                schema["required"] = list(required)
            spec = {"name": name, "description": description, "inputSchema": schema}
            if title:
                spec["title"] = title
            if annotations:
                spec["annotations"] = annotations
            self.tools[name] = (spec, fn)
            return fn

        return register

    def call_tool(self, name, arguments):
        if name not in self.tools:
            raise RpcError(-32602, f"Unknown tool {name}")
        spec, fn = self.tools[name]
        try:
            return text_result(fn(**check(arguments or {}, spec["inputSchema"], "")))
        except Exception as err:  # noqa: BLE001 - every failure is reported to Claude as a tool error
            return error_result(err)

    def handle(self, method, params):
        if method == "initialize":
            return {
                "protocolVersion": params.get("protocolVersion") or LATEST_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": self.info,
            }
        if method == "tools/list":
            return {"tools": [spec for spec, _ in self.tools.values()]}
        if method == "tools/call":
            return self.call_tool(params.get("name"), params.get("arguments"))
        if method == "ping":
            return {}
        raise RpcError(-32601, f"Method not found: {method}")

    def run(self):
        """Serve one JSON-RPC message per line on stdin/stdout until stdin closes."""
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        for line in iter(sys.stdin.readline, ""):
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                self._send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
                continue
            if "id" not in msg:
                continue  # a notification (e.g. "notifications/initialized"): no reply
            try:
                reply = {"jsonrpc": "2.0", "id": msg["id"], "result": self.handle(msg.get("method"), msg.get("params") or {})}
            except RpcError as err:
                reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": err.code, "message": str(err)}}
            except Exception as err:  # noqa: BLE001
                reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": str(err)}}
            self._send(reply)

    @staticmethod
    def _send(msg):
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()
