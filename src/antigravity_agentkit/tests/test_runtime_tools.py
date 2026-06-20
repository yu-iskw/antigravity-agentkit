"""Tests for runtime tool assembly."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from antigravity_agentkit.compiler import compile_from_data
from antigravity_agentkit.loader import load_agent_directory
from antigravity_agentkit.sdk.runtime import create_sdk_config_from_ir


def test_create_sdk_config_from_ir_includes_callable_tools(skills_agent_dir: Path) -> None:
    """Skills compile path includes callable read_skill tools in SDK config."""
    data = load_agent_directory(skills_agent_dir)
    compiled = compile_from_data(data)

    with patch("antigravity_agentkit.sdk.runtime.get_local_agent_config_class") as mock_config:
        mock_cls = MagicMock()
        mock_config.return_value = mock_cls
        with patch(
            "antigravity_agentkit.sdk.runtime.SdkCapabilities.detect",
        ) as mock_detect:
            from antigravity_agentkit.sdk.capabilities import SdkCapabilities

            mock_detect.return_value = SdkCapabilities(
                sdk_version="0.1.4",
                local_agent_config_params=frozenset(
                    {"tools", "skills_paths", "system_instructions"}
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
            create_sdk_config_from_ir(compiled, project_root=skills_agent_dir)
        kwargs = mock_cls.call_args.kwargs
        assert kwargs.get("tools")
        assert kwargs.get("skills_paths")
