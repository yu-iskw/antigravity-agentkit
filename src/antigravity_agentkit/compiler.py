"""Compile agent directory into Antigravity runtime configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.loader import load_agent_directory
from antigravity_agentkit.mcp import (
    compile_mcp_servers,
    parse_mcp_dict,
    try_compile_mcp_sdk_objects,
)
from antigravity_agentkit.policies import compile_policy_dicts, parse_policies_dict
from antigravity_agentkit.runtime_tools import build_read_skill_tool, read_skill_tool_metadata
from antigravity_agentkit.schema.agent import AgentProjectData, CompiledAgentConfig
from antigravity_agentkit.schema.skills import LoadedSkill, SkillIndex
from antigravity_agentkit.sdk import compile_sdk_policies, get_local_agent_config_class
from antigravity_agentkit.skills import build_skill_index
from antigravity_agentkit.subagents import (
    compile_delegation_tools,
    delegation_tool_dict,
)


def render_system_instructions(data: AgentProjectData, skill_index: SkillIndex) -> str:
    """Render system instructions with optional skill index injection."""
    sections = [data.system_instructions.strip()]
    index_section = skill_index.to_prompt_section()
    if index_section:
        sections.append(index_section)
    return "\n\n".join(section for section in sections if section)


def _coerce_skills(skills: dict[str, Any]) -> dict[str, LoadedSkill]:
    """Coerce loaded skills dict to LoadedSkill instances."""
    result: dict[str, LoadedSkill] = {}
    for name, skill in skills.items():
        if isinstance(skill, LoadedSkill):
            result[name] = skill
    return result


def compile_tool_metadata(data: AgentProjectData) -> list[dict[str, Any]]:
    """Compile serializable tool metadata for manifests and registry."""
    tools: list[dict[str, Any]] = []
    if data.subagents:
        for metadata in compile_delegation_tools(data.subagents):
            tools.append(delegation_tool_dict(metadata))
    tools.append(read_skill_tool_metadata(_coerce_skills(data.skills)))
    return tools


def compile_runtime_tools(data: AgentProjectData) -> list[Any]:
    """Compile callable tools for Antigravity SDK runtime."""
    runtime_tools: list[Any] = []
    coerced = _coerce_skills(data.skills)
    if coerced:
        runtime_tools.append(build_read_skill_tool(coerced))
    return runtime_tools


def compile_tools(data: AgentProjectData) -> list[Any]:
    """Compile tool metadata (backward-compatible alias)."""
    return compile_tool_metadata(data)


def compile_vertex_settings(data: AgentProjectData) -> dict[str, Any]:
    """Compile vertex runtime settings."""
    vertex = data.manifest.spec.runtime.vertex
    return {
        "enabled": vertex.enabled,
        "project": vertex.project,
        "location": vertex.location,
    }


def compile_from_data(
    data: AgentProjectData,
    *,
    _production: bool = False,
) -> CompiledAgentConfig:
    """Compile loaded agent project data into runtime configuration."""
    del _production
    skill_index = build_skill_index(_coerce_skills(data.skills))
    system_instructions = render_system_instructions(data, skill_index)

    mcp_servers: list[dict[str, Any]] = []
    if data.mcp_config:
        mcp_servers = compile_mcp_servers(parse_mcp_dict(data.mcp_config))

    policies: list[dict[str, Any]] = []
    if data.policies:
        policies = compile_policy_dicts(parse_policies_dict(data.policies))

    return CompiledAgentConfig(
        system_instructions=system_instructions,
        mcp_servers=mcp_servers,
        tools=compile_tool_metadata(data),
        runtime_tools=compile_runtime_tools(data),
        policies=policies,
        vertex=compile_vertex_settings(data),
        model=data.manifest.spec.runtime.model,
        skill_index=skill_index,
    )


def compile_agent_config(path: str | Path, *, production: bool = False) -> CompiledAgentConfig:
    """Load and compile an agent directory into runtime configuration."""
    data = load_agent_directory(path)
    return compile_from_data(data, _production=production)


def _mcp_config_from_compiled(servers: list[dict[str, Any]]) -> dict[str, Any]:
    """Rebuild mcp.json-shaped config from compiled server dictionaries."""
    mcp_servers: dict[str, Any] = {}
    for server in servers:
        entry: dict[str, Any] = {
            "command": server["command"],
            "args": server.get("args", []),
        }
        if server.get("env"):
            entry["env"] = server["env"]
        mcp_servers[server["name"]] = entry
    return {"mcpServers": mcp_servers}


def compile_to_sdk_config(
    compiled: CompiledAgentConfig,
) -> Any:
    """Convert CompiledAgentConfig to Antigravity LocalAgentConfig when SDK is available."""
    local_agent_config = get_local_agent_config_class()

    kwargs: dict[str, Any] = {
        "system_instructions": compiled.system_instructions,
        "vertex": compiled.vertex.get("enabled", False),
    }
    if compiled.vertex.get("project"):
        kwargs["project"] = compiled.vertex["project"]
    if compiled.vertex.get("location"):
        kwargs["location"] = compiled.vertex["location"]
    if compiled.model:
        kwargs["model"] = compiled.model
    if compiled.mcp_servers:
        mcp_config = _mcp_config_from_compiled(compiled.mcp_servers)
        kwargs["mcp_servers"] = try_compile_mcp_sdk_objects(mcp_config)
    callable_tools = list(compiled.runtime_tools)
    callable_tools.extend(tool for tool in compiled.tools if callable(tool))
    if callable_tools:
        kwargs["tools"] = callable_tools
    if compiled.policies:
        kwargs["policies"] = compile_sdk_policies(compiled.policies)
    return local_agent_config(**kwargs)
