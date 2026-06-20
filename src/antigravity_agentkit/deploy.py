"""Agent Runtime deployment adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.project import AgentProject

_DEPLOY_LABEL = "managed-by"
_DEPLOY_LABEL_VALUE = "antigravity-agentkit"


def build_deployment_config(
    project: AgentProject,
    project_id: str,
    location: str,
) -> dict[str, Any]:
    """Build Agent Engine deployment configuration dictionary."""
    manifest = project.manifest
    deployment = manifest.spec.deployment
    vertex = manifest.spec.runtime.vertex

    display_name = manifest.metadata.display_name or manifest.metadata.name
    if deployment and deployment.display_name:
        display_name = deployment.display_name

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
    }

    if vertex.enabled:
        config["vertex"] = {
            "project": vertex.project or project_id,
            "location": vertex.location or location,
        }

    if deployment:
        if deployment.service_account:
            config["service_account"] = deployment.service_account
        if deployment.min_instances is not None:
            config["min_instances"] = deployment.min_instances
        if deployment.max_instances is not None:
            config["max_instances"] = deployment.max_instances
        if deployment.container_concurrency is not None:
            config["container_concurrency"] = deployment.container_concurrency
        if deployment.resource_limits:
            limits: dict[str, str] = {}
            if deployment.resource_limits.cpu:
                limits["cpu"] = deployment.resource_limits.cpu
            if deployment.resource_limits.memory:
                limits["memory"] = deployment.resource_limits.memory
            if limits:
                config["resource_limits"] = limits
        if deployment.labels:
            config["labels"].update(deployment.labels)
        if deployment.gateway and deployment.gateway.enabled:
            config["gateway"] = deployment.gateway.model_dump(by_alias=True, exclude_none=True)

    return config


def build_source_package(
    project: AgentProject,
    output_dir: str | Path | None = None,
) -> Path:
    """Build a deployable source package from the agent directory."""
    return project.package(output_dir=output_dir)


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


def deploy(
    project: AgentProject,
    project_id: str,
    location: str,
    *,
    output_path: str | Path | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """Deploy agent to Agent Runtime or write config in dry-run mode."""
    package_dir = build_source_package(project)
    config = build_deployment_config(project, project_id, location)
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
        "Live Agent Runtime deployment is not implemented yet. "
        "Use dry_run=True or deploy without GCP credentials to emit config."
    )
