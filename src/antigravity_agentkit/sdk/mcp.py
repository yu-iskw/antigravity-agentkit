"""Compile IR MCP servers to SDK objects."""

from __future__ import annotations

from typing import Any

from antigravity_agentkit.ir import McpServerIR
from antigravity_agentkit.sdk.capabilities import SdkCapabilities
from antigravity_agentkit.sdk.errors import SdkCompatibilityError


def compile_sdk_mcp_servers(
    servers: tuple[McpServerIR, ...],
    *,
    capabilities: SdkCapabilities,
) -> tuple[Any, ...]:
    """Compile MCP server IR to SDK server objects."""
    if not servers:
        return ()

    if not capabilities.accepts_mcp_servers:
        raise SdkCompatibilityError(
            "The installed google-antigravity SDK cannot accept mcp_servers.",
            feature="mcp",
            sdk_version=capabilities.sdk_version,
        )

    try:
        from google.antigravity import types
    except ImportError as exc:
        raise SdkCompatibilityError(
            "google-antigravity is required to compile MCP servers.",
            feature="mcp",
            sdk_version=capabilities.sdk_version,
        ) from exc

    sdk_servers: list[Any] = []
    for server in servers:
        kwargs: dict[str, Any] = {"name": server.name}
        if server.transport == "streamable-http":
            http_server = getattr(types, "McpStreamableHttpServer", None)
            if http_server is None:
                raise SdkCompatibilityError(
                    "The installed SDK does not provide McpStreamableHttpServer.",
                    feature="mcp",
                    sdk_version=capabilities.sdk_version,
                )
            kwargs["url"] = server.url
            sdk_servers.append(http_server(**kwargs))
            continue

        stdio_server = getattr(types, "McpStdioServer", None)
        if stdio_server is None:
            raise SdkCompatibilityError(
                "The installed SDK does not provide McpStdioServer.",
                feature="mcp",
                sdk_version=capabilities.sdk_version,
            )
        kwargs["command"] = server.command
        kwargs["args"] = list(server.args)
        if server.env:
            kwargs["env"] = dict(server.env)
        sdk_servers.append(stdio_server(**kwargs))

    return tuple(sdk_servers)
