"""Agent Platform Runtime live deploy via vertexai agent_engines."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.platform.client import (
    AgentEngineClient,
    create_vertex_agent_engine_client,
)
from antigravity_agentkit.platform.deploy_state import load_deploy_state, record_deploy
from antigravity_agentkit.platform.iam import build_iam_hints_from_config
from antigravity_agentkit.platform.runtime_adapter import (
    PLATFORM_CLASS_METHODS,
    PLATFORM_ENTRYPOINT_MODULE,
    PLATFORM_ENTRYPOINT_OBJECT,
)
from antigravity_agentkit.registry.metadata import PROVENANCE_ENV_GIT_SHA

_MAX_PACKAGE_BYTES = 8 * 1024 * 1024


def package_digest_from_lockfile(package_dir: Path) -> str | None:
    """Return package digest recorded during packaging when available."""
    lock_path = package_dir / "agentkit.lock.json"
    if not lock_path.is_file():
        return None
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    digest = payload.get("packageDigest")
    return str(digest) if digest else None


def package_digest(package_dir: Path) -> str:
    """Return sha256 digest of all files in a package directory."""
    digest = hashlib.sha256()
    for path in sorted(package_dir.rglob("*")):
        if path.is_file() and path.name != "deploy-state.json":
            digest.update(path.relative_to(package_dir).as_posix().encode())
            digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def validate_package_size(package_dir: Path) -> None:
    """Reject packages exceeding Platform source_packages size limit."""
    total = sum(path.stat().st_size for path in package_dir.rglob("*") if path.is_file())
    if total > _MAX_PACKAGE_BYTES:
        raise DeployError(
            f"Source package exceeds Platform 8MB limit ({total} bytes): {package_dir}"
        )


def build_agent_engine_api_config(
    deployment_config: dict[str, Any],
    package_dir: Path,
) -> dict[str, Any]:
    """Map AgentKit deployment-config.json to agent_engines.create config."""
    validate_package_size(package_dir)
    api_config: dict[str, Any] = {
        "source_packages": [str(package_dir)],
        "entrypoint_module": deployment_config.get(
            "entrypoint_module",
            PLATFORM_ENTRYPOINT_MODULE,
        ),
        "entrypoint_object": deployment_config.get(
            "entrypoint_object",
            PLATFORM_ENTRYPOINT_OBJECT,
        ),
        "class_methods": deployment_config.get("class_methods", PLATFORM_CLASS_METHODS),
        "requirements_file": deployment_config.get("requirements_file", "requirements.txt"),
        "display_name": deployment_config.get("display_name", ""),
        "description": deployment_config.get("description", ""),
        "labels": deployment_config.get("labels", {}),
        "agent_framework": deployment_config.get("agent_framework", "custom"),
    }

    optional_keys = (
        "min_instances",
        "max_instances",
        "container_concurrency",
        "resource_limits",
        "service_account",
        "identity_type",
        "env_vars",
    )
    for key in optional_keys:
        if key in deployment_config and deployment_config[key] is not None:
            api_config[key] = deployment_config[key]

    return api_config


def write_iam_hints_sidecar(
    package_dir: Path,
    hints: dict[str, Any],
) -> Path:
    """Write iam-hints.json beside the ship package."""
    path = package_dir / "iam-hints.json"
    path.write_text(json.dumps(hints, indent=2), encoding="utf-8")
    return path


def create_or_update_agent_engine(  # noqa: PLR0913
    deployment_config: dict[str, Any],
    package_dir: Path,
    *,
    project_id: str,
    location: str,
    resource_name: str | None = None,
    wait: bool = True,
    client: AgentEngineClient | None = None,
    mcp_server_names: list[str] | None = None,
) -> dict[str, Any]:
    """Create or update an Agent Runtime reasoning engine."""
    api_config = build_agent_engine_api_config(deployment_config, package_dir)
    engine_client = client or create_vertex_agent_engine_client(project_id, location)

    if resource_name:
        result = engine_client.update(name=resource_name, config=api_config, wait=wait)
    else:
        result = engine_client.create(config=api_config, wait=wait)

    resolved_name = result.get("resourceName") or resource_name or ""
    if not resolved_name:
        raise DeployError("Platform deploy did not return a resource name.")

    digest = package_digest_from_lockfile(package_dir) or package_digest(package_dir)
    git_sha = os.environ.get(PROVENANCE_ENV_GIT_SHA)
    previous = load_deploy_state(package_dir)
    state = record_deploy(
        package_dir,
        resource_name=resolved_name,
        package_digest=digest,
        git_sha=git_sha,
        previous=previous,
    )

    hints = build_iam_hints_from_config(deployment_config, mcp_server_names=mcp_server_names)
    write_iam_hints_sidecar(package_dir, hints)

    return {
        "status": "deployed",
        "resourceName": state.resource_name,
        "packageDigest": state.package_digest,
        "packageDir": str(package_dir),
        "deployedAt": state.deployed_at,
        "displayName": result.get("displayName", ""),
    }


def get_agent_engine_status(
    *,
    project_id: str,
    location: str,
    resource_name: str,
    client: AgentEngineClient | None = None,
) -> dict[str, Any]:
    """Fetch live Agent Engine status."""
    engine_client = client or create_vertex_agent_engine_client(project_id, location)
    result = engine_client.get(name=resource_name)
    return {
        "status": "ok",
        "resourceName": result.get("resourceName", resource_name),
        "displayName": result.get("displayName", ""),
    }


def merge_platform_deploy_fields(
    config: dict[str, Any],
    *,
    env_vars: dict[str, str],
    identity_fields: dict[str, Any],
) -> dict[str, Any]:
    """Merge observability and identity into deployment config (pure helper)."""
    merged = dict(config)
    merged["class_methods"] = PLATFORM_CLASS_METHODS
    merged["entrypoint_module"] = PLATFORM_ENTRYPOINT_MODULE
    merged["entrypoint_object"] = PLATFORM_ENTRYPOINT_OBJECT
    merged["agent_framework"] = "custom"
    if env_vars:
        merged["env_vars"] = env_vars
    merged.update(identity_fields)
    return merged
