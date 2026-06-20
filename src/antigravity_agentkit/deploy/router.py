"""Deploy target router."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from antigravity_agentkit.deploy.agent_platform import (
    build_deployment_config as build_agent_platform_config,
    deploy as deploy_agent_platform,
)
from antigravity_agentkit.deploy.gemini_api import (
    build_deployment_config as build_gemini_api_config,
    deploy as deploy_gemini_api,
)
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest

DeployHandler = tuple[
    Callable[..., dict[str, Any]],
    Callable[..., dict[str, Any]],
]

_TARGET_HANDLERS: dict[str, DeployHandler] = {
    "agent-platform": (build_agent_platform_config, deploy_agent_platform),
    "gemini-api": (build_gemini_api_config, deploy_gemini_api),
}


def _unimplemented_target_error(target: str) -> DeployError:
    supported = ", ".join(sorted(_TARGET_HANDLERS))
    return DeployError(
        f"Deploy target {target!r} is not implemented yet. Supported targets: {supported}."
    )


def _handler_for(target: str) -> DeployHandler:
    handler = _TARGET_HANDLERS.get(target)
    if handler is None:
        raise _unimplemented_target_error(target)
    return handler


def build_deployment_config(
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
) -> dict[str, Any]:
    """Build deployment configuration for the manifest target."""
    build_config, _ = _handler_for(deployment.spec.target)
    return build_config(project, deployment, project_id, location)


def deploy(  # noqa: PLR0913
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
    *,
    output_path: str | Path | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """Deploy or emit deployment artifacts for the manifest target."""
    _, deploy_handler = _handler_for(deployment.spec.target)
    return deploy_handler(
        project,
        deployment,
        project_id,
        location,
        output_path=output_path,
        dry_run=dry_run,
    )
