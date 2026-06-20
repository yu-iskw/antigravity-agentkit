"""Shared deployment helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from antigravity_agentkit.deploy.capabilities import TargetCapabilities
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.ir import CompiledAgentIR
from antigravity_agentkit.registry.metadata import build_registry_metadata
from antigravity_agentkit.schema.deployment import DeploymentManifest

_DEPLOY_LABEL = "managed-by"
_DEPLOY_LABEL_VALUE = "antigravity-agentkit"


def merge_deployment_labels(
    manifest_labels: dict[str, str],
    deploy_labels: dict[str, str],
    agent_name: str,
) -> dict[str, str]:
    """Merge user labels while preserving AgentKit deployment identity."""
    labels = dict(manifest_labels)
    labels.update(deploy_labels)
    labels[_DEPLOY_LABEL] = _DEPLOY_LABEL_VALUE
    labels["agent-name"] = agent_name
    return labels


def resolve_display_name(
    project_display_name: str | None,
    agent_name: str,
    deployment_display_name: str | None,
) -> str:
    """Resolve display name from deployment override or manifest metadata."""
    display_name = project_display_name or agent_name
    if deployment_display_name:
        return deployment_display_name
    return display_name


def has_gcp_credentials() -> bool:
    """Return True when GCP application-default credentials appear configured."""
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    if os.environ.get("CLOUDSDK_AUTH_ACCESS_TOKEN"):
        return True
    try:
        import google.auth  # type: ignore[import-untyped]
        from google.auth.exceptions import DefaultCredentialsError  # type: ignore[import-untyped]
    except ImportError:
        return False

    try:
        google.auth.default()
        return True
    except (DefaultCredentialsError, OSError, ValueError):
        return False


def write_dry_run_artifact(
    path: Path,
    payload: dict[str, Any],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write JSON artifact and return a standard dry-run summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    summary: dict[str, Any] = {
        "status": "dry_run",
        "config_path": str(path),
        "config": payload,
    }
    if extra:
        summary.update(extra)
    return summary


def should_dry_run(*, dry_run: bool | None) -> bool:
    """Return whether deploy should emit artifacts instead of applying live."""
    if dry_run is not None:
        return dry_run
    return not has_gcp_credentials()


def raise_live_deploy_not_implemented(target: str, *, hint: str | None = None) -> None:
    """Raise when live deploy is requested but not implemented for a target."""
    message = f"Live {target} deployment is not implemented yet."
    if hint:
        message = f"{message} {hint}"
    else:
        message = f"{message} Use dry_run=True or deploy without GCP credentials to emit config."
    raise DeployError(message)


def write_registry_metadata_artifact(
    ir: CompiledAgentIR,
    deployment: DeploymentManifest,
    *,
    target: TargetCapabilities,
    location: str,
    path: Path,
) -> Path:
    """Write registry metadata JSON for a deploy target."""
    metadata = build_registry_metadata(
        ir,
        deployment,
        target_name=target.name,
        location=location,
        registry_scope=target.registry_scope,  # pylint: disable=unexpected-keyword-arg
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return path
