"""Map deployment identity settings to Platform API fields."""

from __future__ import annotations

from typing import Any, Literal

from antigravity_agentkit.schema.deployment import DeploymentManifest, IdentityConfig

IdentityMode = Literal["agent-identity", "service-account", "oauth"]

_PLATFORM_IDENTITY_TYPES: dict[IdentityMode, str] = {
    "agent-identity": "AGENT_IDENTITY",
    "service-account": "SERVICE_ACCOUNT",
    "oauth": "OAUTH",
}


def resolve_identity(deployment: DeploymentManifest) -> IdentityConfig:
    """Return effective identity configuration from deployment manifest."""
    if deployment.spec.identity is not None:
        return deployment.spec.identity
    if deployment.spec.service_account:
        return IdentityConfig(
            mode="service-account",
            serviceAccount=deployment.spec.service_account,
        )
    return IdentityConfig(mode="agent-identity")


def identity_api_fields(deployment: DeploymentManifest) -> dict[str, Any]:
    """Build identity_type and service_account keys for agent_engines.create."""
    identity = resolve_identity(deployment)
    fields: dict[str, Any] = {
        "identity_type": _PLATFORM_IDENTITY_TYPES[identity.mode],
    }
    if identity.service_account:
        fields["service_account"] = identity.service_account
    return fields


def build_iam_hints_from_config(
    deployment_config: dict[str, Any],
    *,
    mcp_server_names: list[str] | None = None,
) -> dict[str, Any]:
    """Build IAM hints from deployment config or manifest-derived fields."""
    hints: dict[str, Any] = {
        "runtimeServiceAccount": deployment_config.get("service_account"),
        "identityType": deployment_config.get("identity_type"),
        "recommendedRoles": [
            "roles/aiplatform.user",
            "roles/logging.logWriter",
            "roles/cloudtrace.agent",
        ],
        "mcpServers": mcp_server_names or [],
    }
    gateway = deployment_config.get("gateway")
    if isinstance(gateway, dict):
        endpoints = gateway.get("requiredEndpoints") or gateway.get("required_endpoints")
        if endpoints:
            hints["egressEndpoints"] = list(endpoints)
    return hints


def iam_hints(
    deployment: DeploymentManifest,
    *,
    mcp_server_names: list[str] | None = None,
) -> dict[str, Any]:
    """Document recommended IAM roles (not applied by AgentKit)."""
    identity = resolve_identity(deployment)
    gateway = deployment.spec.gateway
    egress = list(gateway.required_endpoints) if gateway and gateway.enabled else None
    return build_iam_hints_from_config(
        {
            "service_account": identity.service_account,
            "identity_type": _PLATFORM_IDENTITY_TYPES[identity.mode],
            "gateway": {"requiredEndpoints": egress} if egress else None,
        },
        mcp_server_names=mcp_server_names,
    )
