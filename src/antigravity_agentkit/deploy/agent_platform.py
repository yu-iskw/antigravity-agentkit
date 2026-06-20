"""Google Cloud Agent Platform deployment adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from antigravity_agentkit.deploy.package import build_source_package
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest

_DEPLOY_LABEL = "managed-by"
_DEPLOY_LABEL_VALUE = "antigravity-agentkit"


def build_deployment_config(
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
) -> dict[str, Any]:
    """Build Agent Engine deployment configuration dictionary."""
    if deployment.spec.target != "agent-platform":
        raise DeployError(
            f"Deploy target {deployment.spec.target!r} is not implemented yet. "
            "Only 'agent-platform' is supported in M1."
        )

    manifest = project.manifest
    deploy_spec = deployment.spec
    vertex = manifest.spec.runtime.vertex

    display_name = manifest.metadata.display_name or manifest.metadata.name
    if deploy_spec.display_name:
        display_name = deploy_spec.display_name

    config: dict[str, Any] = {
        "source_packages": [str(project.root)],
        "entrypoint_module": "agent",
        "entrypoint_object": "root_agent",
        "requirements_file": "requirements.txt",
        "display_name": display_name,
        "description": manifest.metadata.description or "",
        "labels": {
            _DEPLOY_LABEL: _DEPLOY_LABEL_VALUE,
            "agent-name": manifest.metadata.name,
            **manifest.metadata.labels,
        },
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
    if deploy_spec.labels:
        config["labels"].update(deploy_spec.labels)
    if deploy_spec.gateway and deploy_spec.gateway.enabled:
        config["gateway"] = deploy_spec.gateway.model_dump(by_alias=True, exclude_none=True)

    return config


def _has_gcp_credentials() -> bool:
    """Return True when GCP application-default credentials appear configured."""
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    if os.environ.get("CLOUDSDK_AUTH_ACCESS_TOKEN"):
        return True
    try:
        import google.auth  # type: ignore[import-untyped]

        google.auth.default()
        return True
    except (ImportError, OSError, ValueError):
        return False


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
    package_dir = build_source_package(project)
    config = build_deployment_config(project, deployment, project_id, location)
    config["source_packages"] = [str(package_dir)]

    use_dry_run = dry_run if dry_run is not None else not _has_gcp_credentials()
    if use_dry_run:
        out = Path(output_path or project.root / ".build" / "deployment-config.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return {
            "status": "dry_run",
            "config_path": str(out),
            "package_dir": str(package_dir),
            "config": config,
        }

    raise DeployError(
        "Live Agent Platform deployment is not implemented yet. "
        "Use dry_run=True or deploy without GCP credentials to emit config."
    )
