"""Tests for SDK LocalAgentConfig emission."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from antigravity_agentkit.compiler import compile_agent_config, compile_to_sdk_config
from antigravity_agentkit.exceptions import CompilationError


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
        from google.antigravity import types
    except ImportError:
        pytest.skip("google-antigravity not installed")

    if getattr(types, "SubagentConfig", None) is None:
        with pytest.raises(CompilationError, match="does not support static subagents"):
            compile_to_sdk_config(compiled)
        return

    sdk_config = compile_to_sdk_config(compiled)
    assert sdk_config.capabilities.enable_subagents is True
    assert len(sdk_config.subagents) == 1
    assert sdk_config.subagents[0].name == "proofreader"


def test_compile_to_sdk_config_rejects_constructor_without_subagents(
    subagents_agent_dir: Path,
) -> None:
    """SDK constructors without a subagents parameter fail with an actionable error."""
    compiled = compile_agent_config(subagents_agent_dir)

    def local_config(*, system_instructions: str, vertex: bool) -> None:
        del system_instructions, vertex

    with (
        patch("antigravity_agentkit.sdk.sdk_subagents_supported", return_value=True),
        patch(
            "antigravity_agentkit.sdk.try_compile_sdk_subagents",
            return_value=[object()],
        ),
        patch("antigravity_agentkit.sdk.get_local_agent_config_class", return_value=local_config),
        pytest.raises(CompilationError, match="cannot accept static subagents"),
    ):
        compile_to_sdk_config(compiled)


def test_compile_to_sdk_config_emits_supported_subagents(subagents_agent_dir: Path) -> None:
    """Compatible SDK constructors receive compiled static subagents."""
    compiled = compile_agent_config(subagents_agent_dir)
    received: dict[str, object] = {}

    class FakeSubagentConfig:
        def __init__(self, **kwargs: object) -> None:
            self.name = kwargs["name"]

    def local_config(**kwargs: object) -> dict[str, object]:
        received.update(kwargs)
        return received

    with (
        patch("antigravity_agentkit.sdk.sdk_subagents_supported", return_value=True),
        patch("google.antigravity.types.SubagentConfig", FakeSubagentConfig, create=True),
        patch("antigravity_agentkit.sdk.get_local_agent_config_class", return_value=local_config),
    ):
        sdk_config = compile_to_sdk_config(compiled)

    subagents = sdk_config["subagents"]
    assert isinstance(subagents, list)
    assert subagents[0].name == "proofreader"


def test_compile_to_sdk_config_allows_explicitly_disabled_subagents(
    subagents_agent_dir: Path,
) -> None:
    """Declared subagents do not require SDK support when explicitly disabled."""
    compiled = compile_agent_config(subagents_agent_dir)
    compiled.capabilities["enableSubagents"] = False

    with patch("antigravity_agentkit.sdk.sdk_subagents_supported", return_value=False):
        sdk_config = compile_to_sdk_config(compiled)

    assert sdk_config.capabilities.enable_subagents is False


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


def test_compile_to_sdk_config_emits_skills_paths(skills_agent_dir: Path) -> None:
    """SDK config receives compiled skills_paths when google-antigravity is installed."""
    compiled = compile_agent_config(skills_agent_dir)

    try:
        sdk_config = compile_to_sdk_config(compiled)
    except Exception as exc:
        if "google-antigravity is not installed" in str(exc):
            pytest.skip("google-antigravity not installed")
        raise

    assert sdk_config.skills_paths == compiled.skills_paths
    assert len(sdk_config.skills_paths) == 1
