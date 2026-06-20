"""Tests for SDK LocalAgentConfig emission."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_agentkit.compiler import compile_agent_config, compile_to_sdk_config


def test_compile_to_sdk_config_disables_subagents_by_default(
    hello_world_agent_dir: Path,
) -> None:
    """SDK config preserves the compiled false value for agents without subagents."""
    compiled = compile_agent_config(hello_world_agent_dir)

    try:
        sdk_config = compile_to_sdk_config(compiled)
    except Exception as exc:
        if "google-antigravity is not installed" in str(exc):
            pytest.skip("google-antigravity not installed")
        raise

    assert sdk_config.capabilities.enable_subagents is False


def test_compile_to_sdk_config_includes_subagents_and_capabilities(
    subagents_agent_dir: Path,
) -> None:
    """SDK config receives subagents and capabilities when google-antigravity is installed."""
    compiled = compile_agent_config(subagents_agent_dir)

    try:
        sdk_config = compile_to_sdk_config(compiled)
    except Exception as exc:
        if "google-antigravity is not installed" in str(exc):
            pytest.skip("google-antigravity not installed")
        raise

    assert sdk_config is not None
    assert sdk_config.capabilities is not None
    assert sdk_config.capabilities.enable_subagents is True
    sdk_subagents = getattr(sdk_config, "subagents", None)
    if sdk_subagents:
        assert len(sdk_subagents) == 1
        assert sdk_subagents[0].name == "proofreader"


def test_compile_to_sdk_config_http_mcp_server(hello_world_agent_dir: Path) -> None:
    """SDK config can emit streamable HTTP MCP servers."""
    compiled = compile_agent_config(hello_world_agent_dir)
    compiled.mcp_servers = [
        {
            "name": "remote",
            "transport": "http",
            "url": "https://example.com/mcp",
            "disabledTools": ["dangerous_tool"],
        }
    ]

    try:
        sdk_config = compile_to_sdk_config(compiled)
    except Exception as exc:
        if "google-antigravity is not installed" in str(exc):
            pytest.skip("google-antigravity not installed")
        raise

    assert len(sdk_config.mcp_servers) == 1
    assert sdk_config.mcp_servers[0].url == "https://example.com/mcp"


def test_compile_to_sdk_config_interactive_uses_distinct_handler(
    hello_world_agent_dir: Path,
) -> None:
    """Interactive mode resolves a different ask-user handler than batch mode."""
    from antigravity_agentkit.sdk import resolve_ask_user_handler

    compiled = compile_agent_config(hello_world_agent_dir)
    compiled.policies = [{"tool": "run_command", "decision": "ask_user"}]

    batch_handler = resolve_ask_user_handler(interactive=False)
    interactive_handler = resolve_ask_user_handler(interactive=True)

    assert batch_handler is not interactive_handler
    assert batch_handler(object()) is False

    try:
        compile_to_sdk_config(compiled, interactive=True)
        compile_to_sdk_config(compiled, interactive=False)
    except Exception as exc:
        if "google-antigravity is not installed" in str(exc):
            pytest.skip("google-antigravity not installed")
        raise
