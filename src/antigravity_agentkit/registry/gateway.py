"""Agent Gateway metadata helpers."""

from __future__ import annotations

from antigravity_agentkit.json_types import JsonValue
from antigravity_agentkit.schema.deployment import DeploymentManifest


def build_gateway_metadata(deployment: DeploymentManifest) -> dict[str, JsonValue]:
    """Build gateway section for registry metadata."""
    gateway = deployment.spec.gateway
    if gateway is None or not gateway.enabled:
        return {"enabled": False, "protocols": [], "policyRefs": []}

    return {
        "enabled": True,
        "protocols": ["a2a", "mcp"],
        "policyRefs": [],
    }
