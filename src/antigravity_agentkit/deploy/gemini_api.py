"""Gemini API Managed Agents deployment adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.deploy._common import (
    raise_live_deploy_not_implemented,
    write_dry_run_artifact,
)
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.agent import CompiledAgentConfig
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.schema.skills import LoadedSkill

_BASE_AGENT = "antigravity-preview-05-2026"
_DEFAULT_CONFIG_NAME = "gemini-agent-config.json"


def _inline_skill_sources(project: AgentProject) -> list[dict[str, str]]:
    """Build deterministic inline Managed Agents sources for local skills."""
    sources: list[dict[str, str]] = []
    for name, skill in sorted(project.data.skills.items()):
        if not isinstance(skill, LoadedSkill):
            raise DeployError(f"Gemini API skill {name!r} was not loaded correctly.")
        sources.append(
            {
                "type": "inline",
                "target": f".agents/skills/{skill.name}/SKILL.md",
                "content": skill.content,
            }
        )
    return sources


def _unsupported_features(
    compiled: CompiledAgentConfig,
    *,
    has_non_default_capabilities: bool,
) -> list[str]:
    """Return AgentKit features that cannot be submitted to agents.create."""
    features: list[str] = []
    if compiled.mcp_servers:
        features.append("mcp")
    if compiled.subagents:
        features.append("subagents")
    if compiled.policies:
        features.append("policies")
    if has_non_default_capabilities:
        features.append("capabilities")
    if compiled.vertex.get("enabled"):
        features.append("vertex")
    return features


def _has_non_default_capabilities(project: AgentProject) -> bool:
    """Return whether the manifest explicitly changes capability defaults."""
    capabilities = project.manifest.spec.runtime.capabilities
    return bool(
        capabilities.mode != "restricted"
        or capabilities.enable_subagents is not None
        or capabilities.enabled_tools
        or capabilities.disabled_tools
    )


def build_deployment_config(
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
) -> dict[str, Any]:
    """Build a Gemini API agents.create request body."""
    del project_id, location
    compiled = project.compile()
    unsupported = _unsupported_features(
        compiled,
        has_non_default_capabilities=_has_non_default_capabilities(project),
    )
    if unsupported:
        feature_list = ", ".join(unsupported)
        raise DeployError(f"Gemini API target does not support: {feature_list}.")

    config: dict[str, Any] = {
        "id": deployment.metadata.name,
        "base_agent": _BASE_AGENT,
        "system_instruction": project.data.system_instructions,
    }
    description = project.manifest.metadata.description
    if description:
        config["description"] = description

    sources = _inline_skill_sources(project)
    config["base_environment"] = {"type": "remote", "sources": sources} if sources else "remote"
    return config


def deploy(  # noqa: PLR0913
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
    *,
    output_path: str | Path | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """Emit Gemini API registration contract or raise on live deploy."""
    if dry_run is False:
        raise_live_deploy_not_implemented(
            "Gemini API",
            hint="Use dry_run=True to emit the registration contract.",
        )

    config = build_deployment_config(project, deployment, project_id, location)
    out = Path(output_path or project.root / ".build" / _DEFAULT_CONFIG_NAME)
    return write_dry_run_artifact(out, config)
