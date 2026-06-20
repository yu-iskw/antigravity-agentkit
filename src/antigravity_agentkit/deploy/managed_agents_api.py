"""Managed Agents API deployment adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.deploy._common import (
    write_dry_run_artifact,
    write_registry_metadata_artifact,
)
from antigravity_agentkit.deploy.capabilities import (
    MANAGED_AGENTS_API_CAPABILITIES,
    validate_ir_for_target,
)
from antigravity_agentkit.deploy.target import DeployContext
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.ir import CompiledAgentIR
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.schema.skills import LoadedSkill

_BASE_AGENT = "antigravity-preview-05-2026"
_DEFAULT_CONFIG_NAME = "gemini-agent-config.json"

name = "managed-agents-api"
aliases = ("gemini-api", "managed-agents-api")
capabilities = MANAGED_AGENTS_API_CAPABILITIES


def validate_ir(
    ir: CompiledAgentIR,
    deployment: DeploymentManifest,
    context: DeployContext,
) -> None:
    """Validate IR against Managed Agents API capabilities."""
    del context
    validate_ir_for_target(
        ir,
        deployment,
        capabilities,
        unsupported_hint=(
            "Use target 'agent-platform-runtime' for full-fidelity deployment, or remove "
            "the unsupported features from the agent spec."
        ),
    )


def _inline_skill_sources(project: AgentProject) -> list[dict[str, str]]:
    """Build deterministic inline Managed Agents sources for local skills."""
    sources: list[dict[str, str]] = []
    for skill_name, skill in sorted(project.data.skills.items()):
        if not isinstance(skill, LoadedSkill):
            raise DeployError(f"Managed Agents API skill {skill_name!r} was not loaded correctly.")
        sources.append(
            {
                "type": "inline",
                "target": f".agents/skills/{skill.name}/SKILL.md",
                "content": skill.content,
            }
        )
    return sources


def build_deployment_config(
    project: AgentProject,
    ir: CompiledAgentIR,
    deployment: DeploymentManifest,
) -> dict[str, Any]:
    """Build a Managed Agents API agents.create request body."""
    config: dict[str, Any] = {
        "id": deployment.metadata.name,
        "base_agent": _BASE_AGENT,
        "system_instruction": ir.system_instructions,
    }
    description = project.manifest.metadata.description
    if description:
        config["description"] = description

    sources = _inline_skill_sources(project)
    config["base_environment"] = {"type": "remote", "sources": sources} if sources else "remote"
    config["registry"] = {"scope": capabilities.registry_scope}
    return config


def deploy(  # noqa: PLR0913
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
    *,
    output_path: str | Path | None = None,
    dry_run: bool | None = None,
    resource_name: str | None = None,
    status_only: bool = False,
) -> dict[str, Any]:
    """Emit Managed Agents API registration contract or apply live."""
    del resource_name, status_only
    ir = project.compile()
    context = DeployContext(
        project_id=project_id,
        location=location,
        output_path=Path(output_path) if output_path else None,
        dry_run=dry_run,
    )
    validate_ir(ir, deployment, context)

    config = build_deployment_config(project, ir, deployment)
    out = Path(output_path or project.root / ".build" / _DEFAULT_CONFIG_NAME)

    if dry_run is False:
        from antigravity_agentkit.platform.managed_agents import create_managed_agent

        result = create_managed_agent(config)
        result["config_path"] = str(out)
        return result

    result = write_dry_run_artifact(out, config)

    registry_path = write_registry_metadata_artifact(
        ir,
        deployment,
        target=capabilities,
        location=location,
        path=out.parent / "registry-metadata.json",
    )
    result["registry_metadata_path"] = str(registry_path)
    return result
