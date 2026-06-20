"""Registry metadata builders."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from antigravity_agentkit.ir import CompiledAgentIR
from antigravity_agentkit.json_types import JsonValue
from antigravity_agentkit.platform.iam import resolve_identity
from antigravity_agentkit.registry.gateway import build_gateway_metadata
from antigravity_agentkit.schema.deployment import DeploymentManifest

PROVENANCE_ENV_GIT_SHA = "AGK_GIT_SHA"
PROVENANCE_ENV_PACKAGE_DIGEST = "AGK_PACKAGE_DIGEST"


def provenance_fields(
    git_sha: str | None = None,
    package_digest: str | None = None,
) -> dict[str, str]:
    """Map optional CI inputs to registry metadata provenance keys."""
    provenance: dict[str, str] = {}
    if git_sha:
        provenance["gitSha"] = git_sha
    if package_digest:
        provenance["packageDigest"] = package_digest
    return provenance


def _provenance_from_env() -> dict[str, str]:
    return provenance_fields(
        os.environ.get(PROVENANCE_ENV_GIT_SHA),
        os.environ.get(PROVENANCE_ENV_PACKAGE_DIGEST),
    )


def _registry_scope_for_target(target_name: str) -> str:
    if target_name == "managed-agents-api":
        return "global"
    if target_name == "agent-platform-runtime":
        return "regional"
    return "none"


def build_registry_metadata(
    ir: CompiledAgentIR,
    deployment: DeploymentManifest,
    *,
    target_name: str,
    location: str,
    registry_scope: str | None = None,
) -> dict[str, JsonValue]:
    """Build registry metadata from compiled IR and deployment manifest."""
    agent_name = str(ir.metadata.get("name", deployment.metadata.name))
    display_name = str(ir.metadata.get("displayName", agent_name))
    description = ir.metadata.get("description")
    labels_value = ir.metadata.get("labels", {})
    if isinstance(labels_value, Mapping):
        labels = {str(key): str(value) for key, value in labels_value.items()}
    else:
        labels = {}

    scope = (
        registry_scope if registry_scope is not None else _registry_scope_for_target(target_name)
    )
    identity = resolve_identity(deployment)

    metadata: dict[str, JsonValue] = {
        "agent": {
            "name": agent_name,
            "displayName": display_name,
            "description": description,
            "labels": labels,
        },
        "target": {
            "name": target_name,
            "registryScope": scope,
            "location": location,
        },
        "identity": {
            "mode": identity.mode,
            "serviceAccount": identity.service_account,
        },
        "gateway": build_gateway_metadata(deployment),
        "skills": [
            {
                "name": skill.name,
                "source": skill.source,
                "contentHash": skill.content_hash,
            }
            for skill in ir.skills
        ],
        "mcpServers": [server.name for server in ir.mcp_servers],
        "subagents": [subagent.name for subagent in ir.subagents],
        "policies": {
            "defaultDecision": "deny",
            "ruleCount": len(ir.policies),
        },
        "generatedAt": datetime.now(UTC).isoformat(),
    }
    metadata.update(_provenance_from_env())
    return metadata


def build_mcp_server_metadata(project: Any) -> list[dict[str, Any]]:
    """Build MCP server registry metadata for servers declared in the project."""
    from antigravity_agentkit.mcp import parse_mcp_dict

    data = project.data
    if not data.mcp_config:
        return []

    config = parse_mcp_dict(data.mcp_config)
    servers: list[dict[str, Any]] = []
    for server_name, server in config.mcp_servers.items():
        metadata: dict[str, Any] = {
            "name": server_name,
            "owner": project.manifest.metadata.owner,
            "agentName": project.manifest.metadata.name,
        }
        if server.url:
            metadata.update(
                {
                    "transport": "http",
                    "url": server.url,
                    "headerKeys": sorted(server.headers),
                }
            )
        else:
            metadata.update(
                {
                    "transport": "stdio",
                    "command": server.command,
                    "args": list(server.args),
                    "envKeys": sorted(server.env),
                }
            )
        servers.append(metadata)
    return servers


def build_agent_registry_metadata(
    project: Any,
    deployment: DeploymentManifest,
    *,
    location: str = "",
) -> dict[str, Any]:
    """Backward-compatible registry metadata builder from AgentProject."""
    from antigravity_agentkit.deploy.aliases import resolve_target_name

    ir = project.compile()
    target_name = resolve_target_name(deployment.spec.target)
    return dict(
        build_registry_metadata(
            ir,
            deployment,
            target_name=target_name,
            location=location,
        )
    )


def build_live_registry_payload(
    project: Any,
    deployment: DeploymentManifest,
    *,
    project_id: str,
    location: str,
) -> dict[str, Any]:
    """Build registry metadata with live registration fields."""
    metadata = build_agent_registry_metadata(project, deployment, location=location)
    metadata["registry"] = {
        "project": project_id,
        "location": location,
        "mcpServers": build_mcp_server_metadata(project),
    }
    return metadata
