"""Rollback deployed agents to prior package revisions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.platform.agent_engines import create_or_update_agent_engine
from antigravity_agentkit.platform.client import AgentEngineClient
from antigravity_agentkit.platform.deploy_state import (
    load_deploy_state,
    resolve_rollback_target,
)


def rollback_agent_engine(  # noqa: PLR0913
    deployment_config: dict[str, Any],
    package_dir: Path,
    *,
    project_id: str,
    location: str,
    target: str,
    client: AgentEngineClient | None = None,
) -> dict[str, Any]:
    """Rollback to a prior deploy record using agent_engines.update."""
    state = load_deploy_state(package_dir)
    if state is None:
        raise DeployError(f"No deploy state found at {package_dir}")

    record = resolve_rollback_target(state, target)
    rollback_dir = Path(record.package_dir)
    if not rollback_dir.is_dir():
        raise DeployError(f"Rollback package directory not found: {rollback_dir}")

    resource_name = record.resource_name or state.resource_name
    if not resource_name:
        raise DeployError("Cannot rollback without a resource name in deploy state.")

    result = create_or_update_agent_engine(
        deployment_config,
        rollback_dir,
        project_id=project_id,
        location=location,
        resource_name=resource_name,
        client=client,
        state_package_dir=package_dir,
        git_sha=record.git_sha,
    )
    result["status"] = "rolled_back"
    result["rollbackTarget"] = target
    return result


def deploy_status_summary(
    package_dir: Path,
    *,
    project_id: str,
    location: str,
    resource_name: str | None = None,
    client: AgentEngineClient | None = None,
) -> dict[str, Any]:
    """Combine local deploy-state with live Agent Engine status."""
    from antigravity_agentkit.platform.agent_engines import get_agent_engine_status

    state = load_deploy_state(package_dir)
    summary: dict[str, Any] = {"packageDir": str(package_dir)}
    if state is not None:
        summary["deployState"] = state.to_dict()
        resolved_name = resource_name or state.resource_name
    else:
        resolved_name = resource_name

    if resolved_name:
        summary["live"] = get_agent_engine_status(
            project_id=project_id,
            location=location,
            resource_name=resolved_name,
            client=client,
        )
    else:
        summary["live"] = {"status": "unknown", "message": "No resource name available."}
    return summary
