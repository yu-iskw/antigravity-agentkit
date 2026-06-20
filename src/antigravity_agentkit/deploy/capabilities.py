"""Deploy target capability metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.ir import CompiledAgentIR, default_capabilities_ir
from antigravity_agentkit.schema.deployment import DeploymentManifest


@dataclass(frozen=True)
class TargetCapabilities:
    """Declared feature support for a deploy target."""

    name: str
    fidelity: Literal["full", "reduced"]
    supports_source_package: bool
    supports_inline_skills: bool
    supports_mcp: bool
    supports_static_subagents: bool
    supports_remote_subagents: bool
    supports_policies: bool
    supports_runtime_tools: bool
    supports_capabilities: bool
    supports_vertex_runtime: bool
    supports_live_deploy: bool
    supports_dry_run: bool
    registry_scope: Literal["regional", "global", "none"]
    gateway_metadata_supported: bool
    identity_modes: tuple[Literal["agent-identity", "service-account", "oauth"], ...]


AGENT_PLATFORM_RUNTIME_CAPABILITIES = TargetCapabilities(
    name="agent-platform-runtime",
    fidelity="full",
    supports_source_package=True,
    supports_inline_skills=False,
    supports_mcp=True,
    supports_static_subagents=True,
    supports_remote_subagents=True,
    supports_policies=True,
    supports_runtime_tools=True,
    supports_capabilities=True,
    supports_vertex_runtime=True,
    supports_live_deploy=False,
    supports_dry_run=True,
    registry_scope="regional",
    gateway_metadata_supported=True,
    identity_modes=("agent-identity", "service-account", "oauth"),
)

MANAGED_AGENTS_API_CAPABILITIES = TargetCapabilities(
    name="managed-agents-api",
    fidelity="reduced",
    supports_source_package=False,
    supports_inline_skills=True,
    supports_mcp=False,
    supports_static_subagents=False,
    supports_remote_subagents=False,
    supports_policies=False,
    supports_runtime_tools=False,
    supports_capabilities=False,
    supports_vertex_runtime=False,
    supports_live_deploy=False,
    supports_dry_run=True,
    registry_scope="global",
    gateway_metadata_supported=True,
    identity_modes=("agent-identity",),
)


def unsupported_features_for_target(
    ir: CompiledAgentIR,
    capabilities: TargetCapabilities,
) -> tuple[str, ...]:
    """Return IR features unsupported by the target."""
    unsupported: list[str] = []
    if ir.mcp_servers and not capabilities.supports_mcp:
        unsupported.append("mcp")
    if ir.subagents and not (
        capabilities.supports_static_subagents or capabilities.supports_remote_subagents
    ):
        unsupported.append("subagents")
    if ir.policies and not capabilities.supports_policies:
        unsupported.append("policies")
    if ir.capabilities != default_capabilities_ir() and not capabilities.supports_capabilities:
        unsupported.append("capabilities")
    if ir.vertex.enabled and not capabilities.supports_vertex_runtime:
        unsupported.append("vertex")
    runtime_tools = [
        tool
        for tool in ir.tools
        if tool.kind == "runtime"
        or (tool.kind == "skill-reader" and not capabilities.supports_inline_skills)
    ]
    if runtime_tools and not capabilities.supports_runtime_tools:
        unsupported.append("runtime_tools")
    return tuple(unsupported)


def validate_ir_for_target(
    ir: CompiledAgentIR,
    deployment: DeploymentManifest,
    target: TargetCapabilities,
    *,
    unsupported_hint: str,
) -> None:
    """Raise when IR or deployment options exceed target capabilities."""
    unsupported = unsupported_features_for_target(ir, target)
    if unsupported:
        feature_list = ", ".join(unsupported)
        raise DeployError(
            f"Deploy target {target.name!r} does not support these IR features: {feature_list}. "
            f"{unsupported_hint}"
        )
    if (
        deployment.spec.gateway
        and deployment.spec.gateway.enabled
        and not target.gateway_metadata_supported
    ):
        raise DeployError(f"Deploy target {target.name!r} does not support gateway metadata.")
