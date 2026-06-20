"""Compile agent directory into frozen CompiledAgentIR."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

from antigravity_agentkit.capabilities import compile_capabilities_to_ir
from antigravity_agentkit.ir import (
    IR_SCHEMA_VERSION,
    CompiledAgentIR,
    PolicyRuleIR,
    ToolIR,
    VertexIR,
)
from antigravity_agentkit.json_types import JsonValue
from antigravity_agentkit.mcp import compile_mcp_servers_to_ir, parse_mcp_dict
from antigravity_agentkit.policies import compile_policies_to_ir, parse_policies_dict
from antigravity_agentkit.runtime_tools import read_skill_tool_metadata
from antigravity_agentkit.schema.agent import AgentProjectData
from antigravity_agentkit.schema.skills import LoadedSkill, SkillIndex
from antigravity_agentkit.schema.subagents import LoadedSubagent
from antigravity_agentkit.skills import (
    build_skill_index,
    compile_skills_paths_relative,
    compile_skills_to_ir,
)
from antigravity_agentkit.subagents import (
    compile_subagent_ir,
    compile_subagents_to_ir,
    delegation_tool_dict_from_ir,
    subagent_index_section,
)


def render_system_instructions(
    data: AgentProjectData,
    skill_index: SkillIndex,
    subagent_ir: list[dict[str, object]],
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


def _coerce_skills(skills: dict[str, object]) -> dict[str, LoadedSkill]:
    """Coerce loaded skills dict to LoadedSkill instances."""
    result: dict[str, LoadedSkill] = {}
    for name, skill in skills.items():
        if isinstance(skill, LoadedSkill):
            result[name] = skill
    return result


def _compile_tools_ir(
    subagent_ir: list[dict[str, object]],
    *,
    enable_subagents: bool,
    coerced_skills: dict[str, LoadedSkill],
) -> tuple[ToolIR, ...]:
    """Compile serializable tool metadata for IR."""
    tools: list[ToolIR] = []
    if enable_subagents:
        for entry in subagent_ir:
            delegation = delegation_tool_dict_from_ir(entry)
            tools.append(
                ToolIR(
                    name=str(delegation["name"]),
                    kind="delegation",
                    description=str(delegation.get("description")),
                    metadata={
                        "subagent": delegation.get("subagent"),
                        "tools": delegation.get("tools"),
                        "systemInstructions": delegation.get("system_instructions"),
                    },
                )
            )
    read_skill_meta = read_skill_tool_metadata(coerced_skills)
    tools.append(
        ToolIR(
            name=str(read_skill_meta["name"]),
            kind="skill-reader",
            description=str(read_skill_meta.get("description")),
            metadata={"skills": read_skill_meta.get("skills", [])},
        )
    )
    return tuple(tools)


def _compile_vertex_ir(data: AgentProjectData) -> VertexIR:
    """Compile vertex runtime settings."""
    vertex = data.manifest.spec.runtime.vertex
    return VertexIR(
        enabled=vertex.enabled,
        project=vertex.project,
        location=vertex.location,
    )


def _agent_metadata(data: AgentProjectData) -> dict[str, JsonValue]:
    """Compile manifest metadata for IR."""
    metadata = data.manifest.metadata
    result: dict[str, JsonValue] = {"name": metadata.name}
    if metadata.display_name:
        result["displayName"] = metadata.display_name
    if metadata.description:
        result["description"] = metadata.description
    if metadata.owner:
        result["owner"] = metadata.owner
    if metadata.labels:
        result["labels"] = dict(metadata.labels)
    return result


def _agentkit_version() -> str | None:
    """Return the installed agentkit package version when available."""
    try:
        return importlib.metadata.version("antigravity-agentkit")
    except importlib.metadata.PackageNotFoundError:
        return None


def _coerce_subagents(subagents: dict[str, object]) -> dict[str, LoadedSubagent]:
    """Return loaded subagents for IR compilation."""
    result: dict[str, LoadedSubagent] = {}
    for name, subagent in subagents.items():
        if isinstance(subagent, LoadedSubagent):
            result[name] = subagent
    return result


def compile_from_data(data: AgentProjectData) -> CompiledAgentIR:
    """Compile loaded agent project data into frozen IR."""
    coerced_skills = _coerce_skills(data.skills)
    skill_index = build_skill_index(coerced_skills)
    subagent_dict_ir = compile_subagent_ir(data.subagents)
    capabilities = compile_capabilities_to_ir(
        data.manifest.spec.runtime.capabilities,
        has_subagents=bool(subagent_dict_ir),
    )
    enable_subagents = capabilities.enable_subagents
    system_instructions = render_system_instructions(
        data,
        skill_index,
        subagent_dict_ir,
        enable_subagents=enable_subagents,
    )

    mcp_servers = ()
    if data.mcp_config:
        mcp_servers = compile_mcp_servers_to_ir(parse_mcp_dict(data.mcp_config))

    policies: tuple[PolicyRuleIR, ...] = ()
    if data.policies:
        policies = compile_policies_to_ir(parse_policies_dict(data.policies))

    project_root = data.root
    skills_ir = compile_skills_to_ir(project_root, coerced_skills)
    subagents_ir = compile_subagents_to_ir(project_root, _coerce_subagents(data.subagents))

    return CompiledAgentIR(
        schema_version=IR_SCHEMA_VERSION,
        agentkit_version=_agentkit_version(),
        metadata=_agent_metadata(data),
        system_instructions=system_instructions,
        model=data.manifest.spec.runtime.model,
        vertex=_compile_vertex_ir(data),
        mcp_servers=mcp_servers,
        skills=skills_ir,
        skills_paths=compile_skills_paths_relative(project_root, coerced_skills),
        subagents=subagents_ir,
        tools=_compile_tools_ir(
            subagent_dict_ir,
            enable_subagents=enable_subagents,
            coerced_skills=coerced_skills,
        ),
        policies=policies,
        capabilities=capabilities,
    )


def compile_agent_ir(path: str | Path, *, production: bool = False) -> CompiledAgentIR:
    """Load and compile an agent directory into frozen IR."""
    from antigravity_agentkit.project import AgentProject

    project = AgentProject.load(path)
    if production:
        project.validate(production=True)
    return compile_from_data(project.data)
