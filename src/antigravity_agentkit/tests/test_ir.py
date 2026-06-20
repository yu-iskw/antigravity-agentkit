"""Tests for CompiledAgentIR and JSON serialization."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from antigravity_agentkit.ir import (
    IR_SCHEMA_VERSION,
    CapabilitiesIR,
    CompiledAgentIR,
    McpServerIR,
    PolicyRuleIR,
    SkillIR,
    SubagentIR,
    ToolIR,
    VertexIR,
    capabilities_ir_is_non_default,
    default_capabilities_ir,
)
from antigravity_agentkit.ir_serde import ir_from_dict, ir_from_json, ir_to_dict, ir_to_json


def _sample_ir() -> CompiledAgentIR:
    return CompiledAgentIR(
        schema_version=IR_SCHEMA_VERSION,
        agentkit_version="0.1.0",
        metadata={"name": "example-agent", "labels": {"managed-by": "antigravity-agentkit"}},
        system_instructions="# Example\n\nYou are helpful.",
        model="gemini-3.1-flash-lite",
        vertex=VertexIR(enabled=True, project="my-project", location="asia-northeast1"),
        mcp_servers=(
            McpServerIR(
                name="clock",
                transport="stdio",
                command="python",
                args=("server.py",),
                env={"FOO": "bar"},
                headers={"Authorization": "Bearer token"},
                disabled_tools=("dangerous_tool",),
            ),
        ),
        skills=(
            SkillIR(
                name="greeting-helper",
                path="skills/greeting-helper/SKILL.md",
                content_hash="sha256:abc123",
                description="Greeting helper skill",
            ),
        ),
        skills_paths=("/abs/skills/greeting-helper",),
        subagents=(
            SubagentIR(
                name="researcher",
                type="markdown",
                path="subagents/researcher.md",
                content_hash="sha256:def456",
                description="Research subagent",
                system_instructions="You research topics.",
                tools=("search_web",),
            ),
        ),
        tools=(
            ToolIR(
                name="read_skill",
                kind="skill-reader",
                description="Read a skill by name",
                metadata={"skills": ["greeting-helper"]},
            ),
        ),
        policies=(
            PolicyRuleIR(decision="deny", tool="run_command"),
            PolicyRuleIR(decision="allow", tool="read_skill", default=False),
        ),
        capabilities=CapabilitiesIR(
            mode="restricted",
            enabled_tools=("read_skill",),
            disabled_tools=(),
            enable_subagents=True,
        ),
    )


def test_compiled_agent_ir_is_frozen() -> None:
    ir = _sample_ir()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ir.model = "other"  # type: ignore[misc]


def test_compiled_agent_ir_is_deeply_frozen() -> None:
    ir = _sample_ir()

    with pytest.raises(TypeError):
        ir.metadata["name"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        ir.metadata["labels"]["managed-by"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        ir.mcp_servers[0].env["FOO"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        ir.mcp_servers[0].headers["Authorization"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        ir.tools[0].metadata["skills"] = ()  # type: ignore[index]


def test_ir_json_round_trip() -> None:
    original = _sample_ir()
    restored = ir_from_dict(ir_to_dict(original))
    assert restored == original


def test_ir_json_text_round_trip() -> None:
    original = _sample_ir()
    restored = ir_from_json(ir_to_json(original))
    assert restored == original


def test_json_dumps_succeeds() -> None:
    payload = ir_to_dict(_sample_ir())
    text = json.dumps(payload)
    assert "schemaVersion" in text
    assert "systemInstructions" in text


def test_schema_version_required() -> None:
    ir = _sample_ir()
    assert ir.schema_version == IR_SCHEMA_VERSION


def test_no_path_or_callable_fields() -> None:
    ir = _sample_ir()

    def walk(value: object) -> None:
        assert not isinstance(value, Path)
        assert not callable(value)
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            for field in dataclasses.fields(value):
                walk(getattr(value, field.name))
        elif isinstance(value, Mapping):
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(ir)


def test_default_capabilities_helper() -> None:
    default = default_capabilities_ir()
    assert not capabilities_ir_is_non_default(default)
    assert capabilities_ir_is_non_default(
        CapabilitiesIR(mode="open", enabled_tools=(), disabled_tools=(), enable_subagents=False)
    )
