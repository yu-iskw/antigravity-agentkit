"""Tests for MCP SDK assembly."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest
from google.antigravity import types

from antigravity_agentkit.ir import McpServerIR
from antigravity_agentkit.sdk.errors import SdkCompatibilityError
from antigravity_agentkit.sdk.mcp import compile_sdk_mcp_servers
from antigravity_agentkit.tests.test_sdk_emitter import _full_capabilities


def test_compile_http_mcp_preserves_headers_and_tool_filters() -> None:
    server = McpServerIR(
        name="remote",
        transport="streamable-http",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer token"},
        disabled_tools=("dangerous_tool",),
    )

    compiled = compile_sdk_mcp_servers((server,), capabilities=_full_capabilities())[0]

    assert compiled.headers == {"Authorization": "Bearer token"}
    assert compiled.disabled_tools == ["dangerous_tool"]


def test_compile_sse_mcp_uses_supported_sdk_type() -> None:
    class FakeMcpSseServer:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    server = McpServerIR(
        name="remote",
        transport="sse",
        url="https://example.com/sse",
        enabled_tools=("search",),
    )
    capabilities = replace(_full_capabilities(), has_mcp_sse_server=True)

    with patch.object(types, "McpSseServer", FakeMcpSseServer, create=True):
        compiled = compile_sdk_mcp_servers((server,), capabilities=capabilities)[0]

    assert compiled.kwargs["url"] == "https://example.com/sse"
    assert compiled.kwargs["enabled_tools"] == ["search"]


def test_compile_sse_mcp_rejects_unsupported_sdk() -> None:
    server = McpServerIR(name="remote", transport="sse", url="https://example.com/sse")

    with pytest.raises(SdkCompatibilityError, match="does not provide McpSseServer"):
        compile_sdk_mcp_servers((server,), capabilities=_full_capabilities())
