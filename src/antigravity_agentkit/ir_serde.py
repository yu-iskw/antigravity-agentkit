"""JSON serialization for CompiledAgentIR."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from typing import Any, cast

from antigravity_agentkit.ir import (
    CapabilitiesIR,
    CompiledAgentIR,
    McpServerIR,
    PolicyRuleIR,
    SkillIR,
    SubagentIR,
    ToolIR,
    VertexIR,
)
from antigravity_agentkit.json_types import JsonValue

_CAMEL_OVERRIDES: dict[str, str] = {
    "schema_version": "schemaVersion",
    "agentkit_version": "agentkitVersion",
    "system_instructions": "systemInstructions",
    "mcp_servers": "mcpServers",
    "skills_paths": "skillsPaths",
    "content_hash": "contentHash",
    "registry_ref": "registryRef",
    "enabled_tools": "enabledTools",
    "disabled_tools": "disabledTools",
    "enable_subagents": "enableSubagents",
    "auth_mode": "authMode",
}


def _to_camel(name: str) -> str:
    return _CAMEL_OVERRIDES.get(name, name)


def _from_camel(name: str) -> str:
    for snake, camel in _CAMEL_OVERRIDES.items():
        if camel == name:
            return snake
    return name


def _serialize_value(value: Any) -> JsonValue:
    if is_dataclass(value) and not isinstance(value, type):
        return _serialize_dataclass(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, Sequence):
        return [_serialize_value(item) for item in value]
    raise TypeError(f"IR value is not JSON-serializable: {type(value)!r}")


def _serialize_dataclass(obj: Any) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for field_info in fields(obj):
        key = _to_camel(field_info.name)
        result[key] = _serialize_value(getattr(obj, field_info.name))
    return result


def _mapping(data: dict[str, Any]) -> dict[str, Any]:
    return {_from_camel(key): value for key, value in data.items()}


def _vertex_ir(data: dict[str, Any] | None) -> VertexIR:
    if not data:
        return VertexIR()
    mapped = _mapping(data)
    return VertexIR(
        enabled=bool(mapped.get("enabled", False)),
        project=mapped.get("project"),
        location=mapped.get("location"),
    )


def _capabilities_ir(data: dict[str, Any] | None) -> CapabilitiesIR:
    if not data:
        return CapabilitiesIR()
    mapped = _mapping(data)
    return CapabilitiesIR(
        mode=mapped.get("mode", "restricted"),
        enabled_tools=tuple(mapped.get("enabled_tools") or ()),
        disabled_tools=tuple(mapped.get("disabled_tools") or ()),
        enable_subagents=bool(mapped.get("enable_subagents", False)),
    )


def _mcp_server_ir(data: dict[str, Any]) -> McpServerIR:
    mapped = _mapping(data)
    return McpServerIR(
        name=str(mapped["name"]),
        transport=mapped["transport"],
        command=mapped.get("command"),
        args=tuple(mapped.get("args") or ()),
        url=mapped.get("url"),
        env={str(key): str(value) for key, value in (mapped.get("env") or {}).items()},
        headers={str(key): str(value) for key, value in (mapped.get("headers") or {}).items()},
        enabled_tools=tuple(mapped.get("enabled_tools") or ()),
        disabled_tools=tuple(mapped.get("disabled_tools") or ()),
    )


def _skill_ir(data: dict[str, Any]) -> SkillIR:
    mapped = _mapping(data)
    return SkillIR(
        name=str(mapped["name"]),
        path=str(mapped["path"]),
        content_hash=str(mapped["content_hash"]),
        description=mapped.get("description"),
        source=mapped.get("source", "local"),
        registry_ref=mapped.get("registry_ref"),
        revision=mapped.get("revision"),
    )


def _subagent_ir(data: dict[str, Any]) -> SubagentIR:
    mapped = _mapping(data)
    return SubagentIR(
        name=str(mapped["name"]),
        type=mapped.get("type", "markdown"),
        path=mapped.get("path"),
        content_hash=mapped.get("content_hash"),
        description=mapped.get("description"),
        system_instructions=mapped.get("system_instructions"),
        registry_ref=mapped.get("registry_ref"),
        auth_mode=mapped.get("auth_mode", "agent-identity"),
        tools=tuple(mapped.get("tools") or ()),
    )


def _tool_ir(data: dict[str, Any]) -> ToolIR:
    mapped = _mapping(data)
    return ToolIR(
        name=str(mapped["name"]),
        kind=mapped["kind"],
        description=mapped.get("description"),
        metadata=cast("dict[str, JsonValue]", mapped.get("metadata") or {}),
    )


def _policy_rule_ir(data: dict[str, Any]) -> PolicyRuleIR:
    mapped = _mapping(data)
    return PolicyRuleIR(
        decision=mapped["decision"],
        tool=mapped.get("tool"),
        default=bool(mapped.get("default", False)),
        when=cast("dict[str, JsonValue]", mapped.get("when") or {}),
    )


def ir_to_dict(ir: CompiledAgentIR) -> dict[str, JsonValue]:
    """Serialize CompiledAgentIR to a camelCase JSON-compatible dict."""
    return cast("dict[str, JsonValue]", _serialize_dataclass(ir))


def ir_from_dict(data: dict[str, JsonValue]) -> CompiledAgentIR:
    """Deserialize CompiledAgentIR from a camelCase JSON-compatible dict."""
    mapped = _mapping(cast("dict[str, Any]", data))
    return CompiledAgentIR(
        schema_version=str(mapped["schema_version"]),
        system_instructions=str(mapped["system_instructions"]),
        metadata=cast("dict[str, JsonValue]", mapped.get("metadata") or {}),
        agentkit_version=mapped.get("agentkit_version"),
        model=mapped.get("model"),
        vertex=_vertex_ir(cast("dict[str, Any] | None", mapped.get("vertex"))),
        mcp_servers=tuple(
            _mcp_server_ir(item)
            for item in cast("list[dict[str, Any]]", mapped.get("mcp_servers") or [])
        ),
        skills=tuple(
            _skill_ir(item) for item in cast("list[dict[str, Any]]", mapped.get("skills") or [])
        ),
        skills_paths=tuple(mapped.get("skills_paths") or ()),
        subagents=tuple(
            _subagent_ir(item)
            for item in cast("list[dict[str, Any]]", mapped.get("subagents") or [])
        ),
        tools=tuple(
            _tool_ir(item) for item in cast("list[dict[str, Any]]", mapped.get("tools") or [])
        ),
        policies=tuple(
            _policy_rule_ir(item)
            for item in cast("list[dict[str, Any]]", mapped.get("policies") or [])
        ),
        capabilities=_capabilities_ir(cast("dict[str, Any] | None", mapped.get("capabilities"))),
    )


def ir_to_json(ir: CompiledAgentIR, *, indent: int | None = 2) -> str:
    """Serialize CompiledAgentIR to JSON text."""
    return json.dumps(ir_to_dict(ir), indent=indent, sort_keys=True)


def ir_from_json(text: str) -> CompiledAgentIR:
    """Deserialize CompiledAgentIR from JSON text."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("CompiledAgentIR JSON must be an object")
    return ir_from_dict(cast("dict[str, JsonValue]", data))
