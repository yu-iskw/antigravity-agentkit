"""Tests for SDK runtime assembly from CompiledAgentIR."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from antigravity_agentkit.compiler import compile_agent_ir
from antigravity_agentkit.sdk.capabilities import SdkCapabilities
from antigravity_agentkit.sdk.runtime import create_sdk_config_from_ir


def _full_capabilities() -> SdkCapabilities:
    return SdkCapabilities(
        sdk_version="0.1.4",
        local_agent_config_params=frozenset(
            {
                "system_instructions",
                "model",
                "vertex",
                "project",
                "location",
                "mcp_servers",
                "tools",
                "policies",
                "capabilities",
                "skills_paths",
                "subagents",
            }
        ),
        local_agent_config_accepts_kwargs=False,
        accepts_model=True,
        accepts_vertex=True,
        accepts_project=True,
        accepts_location=True,
        accepts_mcp_servers=True,
        accepts_tools=True,
        accepts_policies=True,
        accepts_capabilities=True,
        accepts_skills_paths=True,
        accepts_subagents=True,
        has_capabilities_config=True,
        has_mcp_stdio_server=True,
        has_mcp_sse_server=False,
        has_mcp_streamable_http_server=True,
        has_subagent_config=True,
        policy_module_path="google.antigravity.policy",
    )


def test_create_sdk_config_disables_subagents_by_default(
    hello_world_agent_dir: Path,
) -> None:
    """Hello world compiles without subagents in SDK config."""
    compiled = compile_agent_ir(hello_world_agent_dir)

    with patch("antigravity_agentkit.sdk.runtime.get_local_agent_config_class") as mock_config:
        mock_cls = MagicMock()
        mock_config.return_value = mock_cls
        with patch(
            "antigravity_agentkit.sdk.runtime.SdkCapabilities.detect",
            return_value=_full_capabilities(),
        ):
            create_sdk_config_from_ir(compiled, project_root=hello_world_agent_dir)
        kwargs = mock_cls.call_args.kwargs
        assert "subagents" not in kwargs or not kwargs.get("subagents")


def test_create_sdk_config_includes_subagents_and_capabilities(
    subagents_agent_dir: Path,
) -> None:
    """Subagents example emits subagents and capabilities when SDK supports them."""
    compiled = compile_agent_ir(subagents_agent_dir)

    with (
        patch(
            "antigravity_agentkit.sdk.runtime.compile_sdk_subagents",
            return_value=(MagicMock(),),
        ),
        patch(
            "antigravity_agentkit.capabilities.try_compile_sdk_capabilities",
            return_value=MagicMock(),
        ),
        patch("antigravity_agentkit.sdk.runtime.get_local_agent_config_class") as mock_config,
    ):
        mock_cls = MagicMock()
        mock_config.return_value = mock_cls
        with patch(
            "antigravity_agentkit.sdk.runtime.SdkCapabilities.detect",
            return_value=_full_capabilities(),
        ):
            create_sdk_config_from_ir(compiled, project_root=subagents_agent_dir)
        kwargs = mock_cls.call_args.kwargs
        assert kwargs.get("subagents")


def test_create_sdk_config_emits_skills_paths(skills_agent_dir: Path) -> None:
    """Skills example includes skills_paths when skills are present."""
    compiled = compile_agent_ir(skills_agent_dir)

    with patch("antigravity_agentkit.sdk.runtime.get_local_agent_config_class") as mock_config:
        mock_cls = MagicMock()
        mock_config.return_value = mock_cls
        with patch(
            "antigravity_agentkit.sdk.runtime.SdkCapabilities.detect",
            return_value=_full_capabilities(),
        ):
            create_sdk_config_from_ir(compiled, project_root=skills_agent_dir)
        kwargs = mock_cls.call_args.kwargs
        assert kwargs.get("skills_paths")
        assert kwargs.get("tools")
