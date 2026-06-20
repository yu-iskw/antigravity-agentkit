"""Google Cloud Agent Platform deployment adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.deploy._common import (
    merge_deployment_labels,
    raise_live_deploy_not_implemented,
    resolve_display_name,
    should_dry_run,
    write_dry_run_artifact,
)
from antigravity_agentkit.deploy.package import build_source_package
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest


def build_deployment_config(
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
) -> dict[str, Any]:
    """Build Agent Engine deployment configuration dictionary."""
    manifest = project.manifest
    deploy_spec = deployment.spec
    vertex = manifest.spec.runtime.vertex

    display_name = resolve_display_name(
        manifest.metadata.display_name,
        manifest.metadata.name,
        deploy_spec.display_name,
    )

    config: dict[str, Any] = {
        "source_packages": [str(project.root)],
        "entrypoint_module": "agent",
        "entrypoint_object": "root_agent",
        "requirements_file": "requirements.txt",
        "display_name": display_name,
        "description": manifest.metadata.description or "",
        "labels": merge_deployment_labels(
            manifest.metadata.labels,
            deploy_spec.labels,
            manifest.metadata.name,
        ),
        "project": project_id,
        "location": location,
        "target": deploy_spec.target,
    }

    if vertex.enabled:
        config["vertex"] = {
            "project": vertex.project or project_id,
            "location": vertex.location or location,
        }

    if deploy_spec.service_account:
        config["service_account"] = deploy_spec.service_account
    if deploy_spec.min_instances is not None:
        config["min_instances"] = deploy_spec.min_instances
    if deploy_spec.max_instances is not None:
        config["max_instances"] = deploy_spec.max_instances
    if deploy_spec.container_concurrency is not None:
        config["container_concurrency"] = deploy_spec.container_concurrency
    if deploy_spec.resource_limits:
        limits: dict[str, str] = {}
        if deploy_spec.resource_limits.cpu:
            limits["cpu"] = deploy_spec.resource_limits.cpu
        if deploy_spec.resource_limits.memory:
            limits["memory"] = deploy_spec.resource_limits.memory
        if limits:
            config["resource_limits"] = limits
    if deploy_spec.gateway and deploy_spec.gateway.enabled:
        config["gateway"] = deploy_spec.gateway.model_dump(by_alias=True, exclude_none=True)

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
    """Deploy agent to Agent Platform or write config in dry-run mode."""
    if not should_dry_run(dry_run=dry_run):
        raise_live_deploy_not_implemented("Agent Platform")

    package_dir = build_source_package(project)
    config = build_deployment_config(project, deployment, project_id, location)
    config["source_packages"] = [str(package_dir)]

    out = Path(output_path or project.root / ".build" / "deployment-config.json")
    return write_dry_run_artifact(out, config, extra={"package_dir": str(package_dir)})
