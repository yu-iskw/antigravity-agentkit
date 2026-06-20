#!/usr/bin/env python3
"""Minimal MCP stdio server exposing UTC clock tools for AgentKit examples."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_utc_time",
        "description": "Return the current UTC time in ISO-8601 format.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "echo",
        "description": "Echo a message (policy-gated in the example agent).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Text to echo"},
            },
            "required": ["message"],
        },
    },
]


def _read_message() -> dict[str, Any] | None:
    """Read one JSON-RPC message from stdin using MCP Content-Length framing."""
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode("utf-8").strip().split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length == 0:
        return None
    body = sys.stdin.buffer.read(length)
    return json.loads(body)


def _write_message(payload: dict[str, Any]) -> None:
    """Write one JSON-RPC message to stdout using MCP Content-Length framing."""
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode())
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _tool_result(req_id: int | str | None, text: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {"content": [{"type": "text", "text": text}], "isError": False},
    }


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    req_id = request.get("id")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "clock-mcp", "version": "0.1.0"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name == "get_utc_time":
            return _tool_result(req_id, datetime.now(tz=UTC).isoformat())
        if name == "echo":
            message = str(arguments.get("message", ""))
            return _tool_result(req_id, message)

    if req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return None


def main() -> None:
    """Run the MCP server until stdin closes."""
    while True:
        message = _read_message()
        if message is None:
            break
        response = _handle(message)
        if response is not None:
            _write_message(response)


if __name__ == "__main__":
    main()
