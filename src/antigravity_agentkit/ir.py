"""Frozen intermediate representation for compiled agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from antigravity_agentkit.json_types import JsonValue

IR_SCHEMA_VERSION = "antigravity-agentkit.ir/v1alpha1"


@dataclass(frozen=True)
class VertexIR:
    """Vertex runtime settings."""

    enabled: bool = False
    project: str | None = None
    location: str | None = None


@dataclass(frozen=True)
class McpServerIR:
    """Compiled MCP server configuration."""

    name: str
    transport: Literal["stdio", "sse", "streamable-http"]
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillIR:
    """Compiled local or registry skill reference."""

    name: str
    path: str
    content_hash: str
    description: str | None = None
    source: Literal["local", "registry"] = "local"
    registry_ref: str | None = None
    revision: str | None = None


@dataclass(frozen=True)
class SubagentIR:
    """Compiled subagent definition."""

    name: str
    type: Literal["markdown", "remote"]
    path: str | None = None
    content_hash: str | None = None
    description: str | None = None
    system_instructions: str | None = None
    registry_ref: str | None = None
    auth_mode: Literal["agent-identity", "service-account", "oauth"] = "agent-identity"
    tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolIR:
    """Serializable tool metadata."""

    name: str
    kind: Literal["skill-reader", "delegation", "mcp", "runtime"]
    description: str | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyRuleIR:
    """Compiled policy rule."""

    decision: Literal["allow", "deny", "ask_user", "require_approval"]
    tool: str | None = None
    default: bool = False
    when: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilitiesIR:
    """Compiled capabilities configuration."""

    mode: Literal["open", "restricted", "locked"] = "restricted"
    enabled_tools: tuple[str, ...] = ()
    disabled_tools: tuple[str, ...] = ()
    enable_subagents: bool = False


def default_capabilities_ir() -> CapabilitiesIR:
    """Return the default capabilities IR used for deploy compatibility checks."""
    return CapabilitiesIR()


def capabilities_ir_is_non_default(caps: CapabilitiesIR) -> bool:
    """Return True when capabilities differ from the deploy default profile."""
    default = default_capabilities_ir()
    return caps != default


@dataclass(frozen=True)
class CompiledAgentIR:
    """Backend-neutral compiled agent contract."""

    schema_version: str
    system_instructions: str
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    agentkit_version: str | None = None
    model: str | None = None
    vertex: VertexIR = field(default_factory=VertexIR)
    mcp_servers: tuple[McpServerIR, ...] = ()
    skills: tuple[SkillIR, ...] = ()
    skills_paths: tuple[str, ...] = ()
    subagents: tuple[SubagentIR, ...] = ()
    tools: tuple[ToolIR, ...] = ()
    policies: tuple[PolicyRuleIR, ...] = ()
    capabilities: CapabilitiesIR = field(default_factory=CapabilitiesIR)
