"""MCP server configuration schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class McpStdioServerConfig(BaseModel):
    """Configuration for a single stdio MCP server."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command: str = Field(..., min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    env_from_secret_manager: dict[str, str] = Field(
        default_factory=dict,
        alias="envFromSecretManager",
    )

    @field_validator("command")
    @classmethod
    def validate_command_not_blank(cls, value: str) -> str:
        """Reject blank command strings."""
        stripped = value.strip()
        if not stripped:
            msg = "MCP server command must not be blank."
            raise ValueError(msg)
        return stripped


# Backward-compatible alias used by compiler modules.
McpServerConfig = McpStdioServerConfig


class McpConfig(BaseModel):
    """Claude/Cursor-style MCP configuration from mcp.json."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mcp_servers: dict[str, McpStdioServerConfig] = Field(
        default_factory=dict,
        alias="mcpServers",
    )

    @field_validator("mcp_servers")
    @classmethod
    def validate_server_names(
        cls,
        value: dict[str, McpStdioServerConfig],
    ) -> dict[str, McpStdioServerConfig]:
        """Reject blank MCP server names."""
        for name in value:
            if not name.strip():
                msg = "MCP server name must not be blank."
                raise ValueError(msg)
        return value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> McpConfig:
        """Build from a raw mcp.json dictionary."""
        return cls.model_validate(data)

    def model_dump_mcp_json(self) -> dict[str, Any]:
        """Serialize to mcp.json-compatible dict with camelCase keys."""
        return self.model_dump(by_alias=True, exclude_none=True)
