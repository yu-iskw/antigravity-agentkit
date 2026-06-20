"""Tests for MCP configuration schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from antigravity_agentkit.schema.mcp import McpConfig
from antigravity_agentkit.tests.schema.conftest import minimal_mcp_dict


def test_mcp_config_rejects_blank_server_name() -> None:
    """MCP server names must not be blank."""
    data = minimal_mcp_dict(mcpServers={"   ": {"command": "python3"}})

    with pytest.raises(ValidationError, match="blank"):
        McpConfig.model_validate(data)


def test_model_dump_mcp_json_round_trip() -> None:
    """model_dump_mcp_json preserves mcpServers shape and aliases."""
    config = McpConfig.model_validate(minimal_mcp_dict())
    dumped = config.model_dump_mcp_json()

    assert "mcpServers" in dumped
    assert dumped["mcpServers"]["clock"]["command"] == "python3"
