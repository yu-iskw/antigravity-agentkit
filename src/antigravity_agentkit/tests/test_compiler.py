"""Tests for agent configuration compilation."""

from __future__ import annotations

from pathlib import Path

from antigravity_agentkit.compiler import compile_agent_config, compile_from_data
from antigravity_agentkit.loader import load_agent_directory
from antigravity_agentkit.schema.agent import CompiledAgentConfig


def test_compile_hello_agent(hello_world_agent_dir: Path) -> None:
    """Compile minimal hello_world example."""
    compiled = compile_agent_config(hello_world_agent_dir)

    assert isinstance(compiled, CompiledAgentConfig)
    assert compiled.model == "gemini-3.1-flash-lite"
    assert "helpful" in compiled.system_instructions.lower()
    assert not compiled.mcp_servers
    assert not compiled.policies
    assert compiled.vertex == {"enabled": False, "project": None, "location": None}
    assert len(compiled.tools) == 1
    assert compiled.tools[0]["name"] == "read_skill"


def test_compile_mcp_example(mcp_agent_dir: Path) -> None:
    """Compile full mcp example."""
    compiled = compile_agent_config(mcp_agent_dir)

    assert compiled.model == "gemini-3.1-flash-lite"
    assert "MCP" in compiled.system_instructions or "time" in compiled.system_instructions.lower()
    assert len(compiled.mcp_servers) == 1
    assert compiled.mcp_servers[0]["name"] == "clock"
    assert compiled.policies
    assert any(rule.get("decision") == "deny" for rule in compiled.policies)
    tool_names = [tool["name"] for tool in compiled.tools if isinstance(tool, dict)]
    assert "read_skill" in tool_names
    assert "delegate_to_time_checker" in tool_names
    delegate_tool = next(
        tool for tool in compiled.tools if tool.get("name") == "delegate_to_time_checker"
    )
    assert delegate_tool["subagent"] == "time-checker"
    assert compiled.skill_index is not None
    assert len(compiled.skill_index.entries) == 1
    assert compiled.subagents
    assert compiled.subagents[0]["name"] == "time-checker"
    assert compiled.capabilities["enableSubagents"] is True


def test_compile_production_does_not_require_deployment(mcp_agent_dir: Path) -> None:
    """Production compilation validates runtime security without ship configuration."""
    compiled = compile_agent_config(mcp_agent_dir, production=True)

    assert compiled.model == "gemini-3.1-flash-lite"


def test_compile_subagents_example(subagents_agent_dir: Path) -> None:
    """Subagents example compiles subagent IR and enables subagents."""
    compiled = compile_agent_config(subagents_agent_dir)

    assert len(compiled.subagents) == 1
    assert compiled.subagents[0]["name"] == "proofreader"
    assert compiled.capabilities["enableSubagents"] is True
    assert "## Available Subagents" in compiled.system_instructions


def test_compile_locked_mode_disables_dangerous_tools(hello_world_agent_dir: Path) -> None:
    """Locked capabilities mode adds default disabled builtin tools."""
    data = load_agent_directory(hello_world_agent_dir)
    data.manifest.spec.runtime.capabilities.mode = "locked"
    compiled = compile_from_data(data)

    assert "run_command" in compiled.capabilities["disabledTools"]
    assert "create_file" in compiled.capabilities["disabledTools"]


def test_compile_injects_skill_index_into_instructions(skills_agent_dir: Path) -> None:
    """Compiled system instructions include the skill index section."""
    data = load_agent_directory(skills_agent_dir)
    compiled = compile_from_data(data)

    assert "## Available Skills" in compiled.system_instructions
    assert "greeting-helper" in compiled.system_instructions
    assert len(compiled.skills_paths) == 1
    assert compiled.skills_paths[0].endswith("skills/greeting-helper")


def test_compile_vertex_settings_from_manifest(mcp_agent_dir: Path) -> None:
    """Vertex settings are compiled from agent.yaml runtime spec."""
    compiled = compile_agent_config(mcp_agent_dir)

    assert compiled.vertex["enabled"] is False
    assert compiled.vertex["project"] is None
