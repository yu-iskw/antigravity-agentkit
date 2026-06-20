"""Tests for deploy target capabilities."""

from __future__ import annotations

from antigravity_agentkit.deploy.capabilities import (
    MANAGED_AGENTS_API_CAPABILITIES,
    unsupported_features_for_target,
)
from antigravity_agentkit.ir import (
    IR_SCHEMA_VERSION,
    CapabilitiesIR,
    CompiledAgentIR,
    McpServerIR,
    PolicyRuleIR,
    SubagentIR,
    VertexIR,
)


def _base_ir() -> CompiledAgentIR:
    return CompiledAgentIR(
        schema_version=IR_SCHEMA_VERSION,
        system_instructions="# Agent",
    )


def test_managed_agents_rejects_mcp() -> None:
    ir = CompiledAgentIR(
        schema_version=IR_SCHEMA_VERSION,
        system_instructions="# Agent",
        mcp_servers=(
            McpServerIR(name="clock", transport="stdio", command="python", args=("server.py",)),
        ),
    )
    assert unsupported_features_for_target(ir, MANAGED_AGENTS_API_CAPABILITIES) == ("mcp",)


def test_managed_agents_rejects_subagents() -> None:
    ir = CompiledAgentIR(
        schema_version=IR_SCHEMA_VERSION,
        system_instructions="# Agent",
        subagents=(SubagentIR(name="helper", type="markdown"),),
    )
    assert unsupported_features_for_target(ir, MANAGED_AGENTS_API_CAPABILITIES) == ("subagents",)


def test_managed_agents_rejects_policies() -> None:
    ir = CompiledAgentIR(
        schema_version=IR_SCHEMA_VERSION,
        system_instructions="# Agent",
        policies=(PolicyRuleIR(decision="deny", tool="run_command"),),
    )
    assert unsupported_features_for_target(ir, MANAGED_AGENTS_API_CAPABILITIES) == ("policies",)


def test_managed_agents_rejects_vertex() -> None:
    ir = CompiledAgentIR(
        schema_version=IR_SCHEMA_VERSION,
        system_instructions="# Agent",
        vertex=VertexIR(enabled=True, project="p", location="us-central1"),
    )
    assert unsupported_features_for_target(ir, MANAGED_AGENTS_API_CAPABILITIES) == ("vertex",)


def test_managed_agents_rejects_non_default_capabilities() -> None:
    ir = CompiledAgentIR(
        schema_version=IR_SCHEMA_VERSION,
        system_instructions="# Agent",
        capabilities=CapabilitiesIR(mode="open"),
    )
    assert unsupported_features_for_target(ir, MANAGED_AGENTS_API_CAPABILITIES) == ("capabilities",)


def test_minimal_ir_supported_by_managed_agents() -> None:
    assert not unsupported_features_for_target(_base_ir(), MANAGED_AGENTS_API_CAPABILITIES)
