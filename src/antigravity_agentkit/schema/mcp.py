"""MCP server configuration schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class McpServerConfig(BaseModel):
    """Configuration for a single MCP server (stdio or streamable HTTP)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    env_from_secret_manager: dict[str, str] = Field(
        default_factory=dict,
        alias="envFromSecretManager",
    )
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    enabled_tools: list[str] = Field(default_factory=list, alias="enabledTools")
    disabled_tools: list[str] = Field(default_factory=list, alias="disabledTools")

    @field_validator("command")
    @classmethod
    def validate_command_not_blank(cls, value: str | None) -> str | None:
        """Reject blank command strings."""
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            msg = "MCP server command must not be blank."
            raise ValueError(msg)
        return stripped

    @field_validator("url")
    @classmethod
    def validate_url_not_blank(cls, value: str | None) -> str | None:
        """Reject blank URL strings."""
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            msg = "MCP server url must not be blank."
            raise ValueError(msg)
        return stripped

    @model_validator(mode="after")
    def validate_transport(self) -> McpServerConfig:
        """Require exactly one of url (HTTP) or command (stdio)."""
        has_url = bool(self.url)
        has_command = bool(self.command)
        if has_url == has_command:
            msg = "MCP server must declare exactly one of 'url' or 'command'."
            raise ValueError(msg)
        return self


# Backward-compatible alias used by older imports.
McpStdioServerConfig = McpServerConfig


class McpConfig(BaseModel):
    """Claude/Cursor-style MCP configuration from mcp.json."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mcp_servers: dict[str, McpServerConfig] = Field(
        default_factory=dict,
        alias="mcpServers",
    )

    @field_validator("mcp_servers")
    @classmethod
    def validate_server_names(
        cls,
        value: dict[str, McpServerConfig],
    ) -> dict[str, McpServerConfig]:
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
