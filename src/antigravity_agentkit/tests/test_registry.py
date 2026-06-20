"""Tests for Agent Registry and MCP registry metadata."""

from __future__ import annotations

import json
from pathlib import Path

from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.registry import build_mcp_server_metadata


def test_build_stdio_mcp_server_metadata(mcp_agent_dir: Path) -> None:
    """Stdio registry metadata contains only stdio connection fields."""
    project = AgentProject.load(mcp_agent_dir)

    metadata = build_mcp_server_metadata(project)[0]

    assert metadata["transport"] == "stdio"
    assert metadata["command"] == "python3"
    assert metadata["args"] == ["server/clock_mcp.py"]
    assert "url" not in metadata
    assert "headerKeys" not in metadata


def test_build_http_mcp_server_metadata_excludes_header_values(
    hello_world_agent_dir: Path,
) -> None:
    """HTTP registry metadata exposes header names without secret values."""
    project = AgentProject.load(hello_world_agent_dir)
    project.data.mcp_config = {
        "mcpServers": {
            "remote": {
                "url": "https://example.com/mcp",
                "headers": {
                    "Authorization": "Bearer ${TOKEN}",
                    "X-Trace-Id": "private-trace-value",
                },
            }
        }
    }

    metadata = build_mcp_server_metadata(project)[0]

    assert metadata["transport"] == "http"
    assert metadata["url"] == "https://example.com/mcp"
    assert metadata["headerKeys"] == ["Authorization", "X-Trace-Id"]
    assert "command" not in metadata
    assert "args" not in metadata
    assert "envKeys" not in metadata
    serialized = json.dumps(metadata)
    assert "Bearer ${TOKEN}" not in serialized
    assert "private-trace-value" not in serialized
