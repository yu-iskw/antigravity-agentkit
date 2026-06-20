"""Frozen intermediate representation for compiled agents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from antigravity_agentkit.json_types import JsonValue

IR_SCHEMA_VERSION = "antigravity-agentkit.ir/v1alpha1"


def _freeze_json_value(value: JsonValue) -> JsonValue:
    """Recursively convert JSON containers to immutable equivalents."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json_value(item) for key, item in value.items()})
    if isinstance(value, Sequence):
        return tuple(_freeze_json_value(item) for item in value)
    raise TypeError(f"IR value is not JSON-compatible: {type(value)!r}")


def _freeze_json_mapping(value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
    frozen = _freeze_json_value(value)
    if not isinstance(frozen, Mapping):
        raise TypeError("IR mapping value must be a mapping")
    return frozen


def _freeze_string_mapping(value: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(value))


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
    env: Mapping[str, str] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    enabled_tools: tuple[str, ...] = ()
    disabled_tools: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "env", _freeze_string_mapping(self.env))
        object.__setattr__(self, "headers", _freeze_string_mapping(self.headers))
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "enabled_tools", tuple(self.enabled_tools))
        object.__setattr__(self, "disabled_tools", tuple(self.disabled_tools))


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "tools", tuple(self.tools))


@dataclass(frozen=True)
class ToolIR:
    """Serializable tool metadata."""

    name: str
    kind: Literal["skill-reader", "delegation", "mcp", "runtime"]
    description: str | None = None
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_json_mapping(self.metadata))


@dataclass(frozen=True)
class PolicyRuleIR:
    """Compiled policy rule."""

    decision: Literal["allow", "deny", "ask_user", "require_approval"]
    tool: str | None = None
    default: bool = False
    when: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "when", _freeze_json_mapping(self.when))


@dataclass(frozen=True)
class CapabilitiesIR:
    """Compiled capabilities configuration."""

    mode: Literal["open", "restricted", "locked"] = "restricted"
    enabled_tools: tuple[str, ...] = ()
    disabled_tools: tuple[str, ...] = ()
    enable_subagents: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "enabled_tools", tuple(self.enabled_tools))
        object.__setattr__(self, "disabled_tools", tuple(self.disabled_tools))


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
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_json_mapping(self.metadata))
        object.__setattr__(self, "mcp_servers", tuple(self.mcp_servers))
        object.__setattr__(self, "skills", tuple(self.skills))
        object.__setattr__(self, "skills_paths", tuple(self.skills_paths))
        object.__setattr__(self, "subagents", tuple(self.subagents))
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "policies", tuple(self.policies))
