"""Deploy target router."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.deploy import agent_platform_runtime, managed_agents_api
from antigravity_agentkit.deploy.aliases import resolve_target_name
from antigravity_agentkit.deploy.target import DeployContext
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest

_TARGET_MODULES = {
    "agent-platform-runtime": agent_platform_runtime,
    "managed-agents-api": managed_agents_api,
}


def _module_for(target: str) -> Any:
    canonical = resolve_target_name(target)
    module = _TARGET_MODULES.get(canonical)
    if module is None:
        supported = ", ".join(sorted(_TARGET_MODULES))
        raise DeployError(
            f"Deploy target {target!r} is not implemented yet. Supported targets: {supported}."
        )
    return module


def build_deployment_config(
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
) -> dict[str, Any]:
    """Build deployment configuration for the manifest target."""
    module = _module_for(deployment.spec.target)
    ir = project.compile()
    module.validate_ir(
        ir,
        deployment,
        DeployContext(project_id=project_id, location=location),
    )
    if module.name == "managed-agents-api":
        return module.build_deployment_config(project, ir, deployment)
    return module.build_deployment_config(
        project,
        ir,
        deployment,
        project_id,
        location,
    )


def deploy(  # noqa: PLR0913
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
    *,
    output_path: str | Path | None = None,
    dry_run: bool | None = None,
    resource_name: str | None = None,
    wait: bool = True,
    status_only: bool = False,
) -> dict[str, Any]:
    """Deploy or emit deployment artifacts for the manifest target."""
    module = _module_for(deployment.spec.target)
    return module.deploy(
        project,
        deployment,
        project_id,
        location,
        output_path=output_path,
        dry_run=dry_run,
        resource_name=resource_name,
        wait=wait,
        status_only=status_only,
    )
