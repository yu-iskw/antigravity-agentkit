"""Compile agent directory into Antigravity runtime configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.capabilities import compile_capabilities_ir
from antigravity_agentkit.mcp import compile_mcp_servers, parse_mcp_dict
from antigravity_agentkit.policies import compile_policy_dicts, parse_policies_dict
from antigravity_agentkit.runtime_tools import build_read_skill_tool, read_skill_tool_metadata
from antigravity_agentkit.schema.agent import AgentProjectData, CompiledAgentConfig
from antigravity_agentkit.schema.skills import LoadedSkill, SkillIndex
from antigravity_agentkit.sdk import compile_to_sdk_config_from_compiled
from antigravity_agentkit.skills import build_skill_index, compile_skills_paths
from antigravity_agentkit.subagents import (
    compile_subagent_ir,
    delegation_tool_dict_from_ir,
    subagent_index_section,
)


def render_system_instructions(
    data: AgentProjectData,
    skill_index: SkillIndex,
    subagent_ir: list[dict[str, Any]],
    *,
    enable_subagents: bool,
) -> str:
    """Render system instructions with optional skill and subagent sections."""
    sections = [data.system_instructions.strip()]
    index_section = skill_index.to_prompt_section()
    if index_section:
        sections.append(index_section)
    subagent_section = subagent_index_section(
        subagent_ir,
        enable_subagents=enable_subagents,
    )
    if subagent_section:
        sections.append(subagent_section)
    return "\n\n".join(section for section in sections if section)


def _coerce_skills(skills: dict[str, Any]) -> dict[str, LoadedSkill]:
    """Coerce loaded skills dict to LoadedSkill instances."""
    result: dict[str, LoadedSkill] = {}
    for name, skill in skills.items():
        if isinstance(skill, LoadedSkill):
            result[name] = skill
    return result


def compile_tool_metadata(
    data: AgentProjectData,
    subagent_ir: list[dict[str, Any]],
    *,
    enable_subagents: bool,
    coerced_skills: dict[str, LoadedSkill] | None = None,
) -> list[dict[str, Any]]:
    """Compile serializable tool metadata for manifests and registry."""
    skills = coerced_skills if coerced_skills is not None else _coerce_skills(data.skills)
    tools: list[dict[str, Any]] = []
    if enable_subagents:
        tools.extend(delegation_tool_dict_from_ir(entry) for entry in subagent_ir)
    tools.append(read_skill_tool_metadata(skills))
    return tools


def compile_runtime_tools(
    data: AgentProjectData,
    *,
    coerced_skills: dict[str, LoadedSkill] | None = None,
) -> list[Any]:
    """Compile callable tools for Antigravity SDK runtime."""
    skills = coerced_skills if coerced_skills is not None else _coerce_skills(data.skills)
    runtime_tools: list[Any] = []
    if skills:
        runtime_tools.append(build_read_skill_tool(skills))
    return runtime_tools


def compile_vertex_settings(data: AgentProjectData) -> dict[str, Any]:
    """Compile vertex runtime settings."""
    vertex = data.manifest.spec.runtime.vertex
    return {
        "enabled": vertex.enabled,
        "project": vertex.project,
        "location": vertex.location,
    }


def compile_from_data(data: AgentProjectData) -> CompiledAgentConfig:
    """Compile loaded agent project data into runtime configuration."""
    coerced_skills = _coerce_skills(data.skills)
    skill_index = build_skill_index(coerced_skills)
    skills_paths = compile_skills_paths(coerced_skills)
    subagents = compile_subagent_ir(data.subagents)
    capabilities = compile_capabilities_ir(
        data.manifest.spec.runtime.capabilities,
        has_subagents=bool(subagents),
    )
    enable_subagents = bool(capabilities["enableSubagents"])
    system_instructions = render_system_instructions(
        data,
        skill_index,
        subagents,
        enable_subagents=enable_subagents,
    )

    mcp_servers: list[dict[str, Any]] = []
    if data.mcp_config:
        mcp_servers = compile_mcp_servers(parse_mcp_dict(data.mcp_config))

    policies: list[dict[str, Any]] = []
    if data.policies:
        policies = compile_policy_dicts(parse_policies_dict(data.policies))

    return CompiledAgentConfig(
        system_instructions=system_instructions,
        mcp_servers=mcp_servers,
        tools=compile_tool_metadata(
            data,
            subagents,
            enable_subagents=enable_subagents,
            coerced_skills=coerced_skills,
        ),
        runtime_tools=compile_runtime_tools(data, coerced_skills=coerced_skills),
        policies=policies,
        capabilities=capabilities,
        subagents=subagents,
        vertex=compile_vertex_settings(data),
        model=data.manifest.spec.runtime.model,
        skill_index=skill_index,
        skills_paths=skills_paths,
    )


def compile_agent_config(path: str | Path, *, production: bool = False) -> CompiledAgentConfig:
    """Load and compile an agent directory into runtime configuration."""
    from antigravity_agentkit.project import AgentProject

    project = AgentProject.load(path)
    if production:
        project.validate(production=True)
    return compile_from_data(project.data)


def compile_to_sdk_config(
    compiled: CompiledAgentConfig,
    *,
    interactive: bool = False,
) -> Any:
    """Convert CompiledAgentConfig to Antigravity LocalAgentConfig when SDK is available."""
    return compile_to_sdk_config_from_compiled(compiled, interactive=interactive)
