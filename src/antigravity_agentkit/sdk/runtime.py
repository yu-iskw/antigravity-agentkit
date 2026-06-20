"""Assemble CompiledAgentIR into SDK runtime objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from antigravity_agentkit.capabilities import (
    capabilities_ir_to_sdk_dict,
    try_compile_sdk_capabilities,
)
from antigravity_agentkit.ir import CompiledAgentIR
from antigravity_agentkit.ir_serde import ir_from_json
from antigravity_agentkit.runtime_tools import build_read_skill_tool
from antigravity_agentkit.schema.skills import LoadedSkill
from antigravity_agentkit.sdk.capabilities import SdkCapabilities
from antigravity_agentkit.sdk.errors import ANTIGRAVITY_INSTALL_HINT, SdkCompatibilityError
from antigravity_agentkit.sdk.mcp import compile_sdk_mcp_servers
from antigravity_agentkit.sdk.policies import compile_sdk_policies, resolve_ask_user_handler
from antigravity_agentkit.sdk.subagents import compile_sdk_subagents
from antigravity_agentkit.skills import load_skill_md


@dataclass(frozen=True)
class RuntimeAssembly:
    """Non-serializable SDK preparation artifacts."""

    sdk_config_kwargs: dict[str, Any]
    runtime_tools: tuple[Any, ...]
    sdk_mcp_servers: tuple[Any, ...]
    sdk_policies: tuple[Any, ...]
    sdk_subagents: tuple[Any, ...]


def _load_skills_from_ir(ir: CompiledAgentIR, project_root: Path) -> dict[str, LoadedSkill]:
    skills: dict[str, LoadedSkill] = {}
    for skill_ir in ir.skills:
        skill_path = (project_root / skill_ir.path).resolve()
        skills[skill_ir.name] = load_skill_md(skill_path)
    return skills


def _resolve_skills(
    ir: CompiledAgentIR,
    project_root: Path,
    loaded_skills: dict[str, LoadedSkill] | None,
) -> dict[str, LoadedSkill]:
    if loaded_skills is not None:
        return loaded_skills
    return _load_skills_from_ir(ir, project_root)


def _absolute_skills_paths(ir: CompiledAgentIR, project_root: Path) -> list[str]:
    return [str((project_root / rel_path).resolve()) for rel_path in ir.skills_paths]


def get_local_agent_config_class() -> type[Any]:
    try:
        from google.antigravity import LocalAgentConfig
    except ImportError as exc:
        raise SdkCompatibilityError(
            ANTIGRAVITY_INSTALL_HINT,
            feature="sdk",
            sdk_version=None,
        ) from exc
    return LocalAgentConfig


def get_agent_class() -> type[Any]:
    try:
        from google.antigravity import Agent
    except ImportError as exc:
        raise SdkCompatibilityError(
            ANTIGRAVITY_INSTALL_HINT,
            feature="sdk",
            sdk_version=None,
        ) from exc
    return Agent


def assemble(
    ir: CompiledAgentIR,
    *,
    project_root: str | Path,
    capabilities: SdkCapabilities | None = None,
    interactive: bool = False,
    loaded_skills: dict[str, LoadedSkill] | None = None,
) -> RuntimeAssembly:
    """Assemble SDK runtime objects from IR and project context."""
    root = Path(project_root).resolve()
    caps = capabilities or SdkCapabilities.detect()
    ask_user_handler = resolve_ask_user_handler(interactive=interactive)

    kwargs: dict[str, Any] = {
        "system_instructions": ir.system_instructions,
        "vertex": ir.vertex.enabled,
    }
    if ir.vertex.project and caps.accepts_project:
        kwargs["project"] = ir.vertex.project
    if ir.vertex.location and caps.accepts_location:
        kwargs["location"] = ir.vertex.location
    if ir.model and caps.accepts_model:
        kwargs["model"] = ir.model

    sdk_mcp_servers = compile_sdk_mcp_servers(ir.mcp_servers, capabilities=caps)
    if sdk_mcp_servers:
        kwargs["mcp_servers"] = list(sdk_mcp_servers)

    skills = _resolve_skills(ir, root, loaded_skills)
    runtime_tools: list[Any] = []
    if skills:
        if not caps.accepts_skills_paths:
            raise SdkCompatibilityError(
                "The installed google-antigravity SDK cannot accept skills_paths.",
                feature="skills_paths",
                sdk_version=caps.sdk_version,
            )
        kwargs["skills_paths"] = _absolute_skills_paths(ir, root)
        if caps.accepts_tools:
            runtime_tools.append(build_read_skill_tool(skills))

    sdk_capabilities = try_compile_sdk_capabilities(capabilities_ir_to_sdk_dict(ir.capabilities))
    if sdk_capabilities is not None:
        if not caps.accepts_capabilities:
            raise SdkCompatibilityError(
                "The installed google-antigravity SDK cannot accept capabilities.",
                feature="capabilities",
                sdk_version=caps.sdk_version,
            )
        kwargs["capabilities"] = sdk_capabilities

    sdk_subagents = ()
    if ir.capabilities.enable_subagents and ir.subagents:
        if not caps.has_subagent_config or not caps.accepts_subagents:
            raise SdkCompatibilityError(
                "The installed google-antigravity SDK cannot accept static subagents.",
                feature="subagents",
                sdk_version=caps.sdk_version,
            )
        sdk_subagents = compile_sdk_subagents(ir.subagents, capabilities=caps)
        kwargs["subagents"] = list(sdk_subagents)

    sdk_policies = compile_sdk_policies(
        ir.policies,
        capabilities=caps,
        ask_user_handler=ask_user_handler,
    )
    if sdk_policies:
        kwargs["policies"] = list(sdk_policies)

    if runtime_tools:
        kwargs["tools"] = list(runtime_tools)

    return RuntimeAssembly(
        sdk_config_kwargs=kwargs,
        runtime_tools=tuple(runtime_tools),
        sdk_mcp_servers=sdk_mcp_servers,
        sdk_policies=sdk_policies,
        sdk_subagents=sdk_subagents,
    )


def create_sdk_config_from_ir(
    ir: CompiledAgentIR,
    *,
    project_root: str | Path,
    interactive: bool = False,
    loaded_skills: dict[str, LoadedSkill] | None = None,
) -> Any:
    """Create a LocalAgentConfig from compiled IR."""
    assembly = assemble(
        ir,
        project_root=project_root,
        interactive=interactive,
        loaded_skills=loaded_skills,
    )
    local_agent_config = get_local_agent_config_class()
    return local_agent_config(**assembly.sdk_config_kwargs)


def create_agent_from_ir(
    ir: CompiledAgentIR,
    *,
    project_root: str | Path,
    interactive: bool = False,
    loaded_skills: dict[str, LoadedSkill] | None = None,
) -> Any:
    """Create an Antigravity SDK Agent from compiled IR."""
    sdk_config = create_sdk_config_from_ir(
        ir,
        project_root=project_root,
        interactive=interactive,
        loaded_skills=loaded_skills,
    )
    return get_agent_class()(sdk_config)


def create_agent_from_ir_file(
    path: str | Path,
    *,
    project_root: str | Path = ".",
) -> Any:
    """Create an Antigravity SDK Agent from a serialized IR JSON file."""
    ir_path = Path(path)
    if not ir_path.is_absolute():
        ir_path = Path(project_root).resolve() / ir_path
    ir = ir_from_json(ir_path.read_text(encoding="utf-8"))
    return create_agent_from_ir(ir, project_root=project_root)
