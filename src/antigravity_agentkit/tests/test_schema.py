"""Tests for AgentManifest and related schema validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from antigravity_agentkit.loader import load_agent_yaml
from antigravity_agentkit.schema.agent import AgentManifest


def _minimal_manifest_dict(**overrides: object) -> dict:
    """Build a minimal valid manifest dict with optional overrides."""
    base = {
        "apiVersion": "antigravity-agentkit.dev/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "name": "test-agent",
            "displayName": "Test Agent",
        },
        "spec": {
            "instructions": {"system": "SYSTEM.md"},
        },
    }
    for key, value in overrides.items():
        if key == "metadata" and isinstance(value, dict):
            base["metadata"].update(value)
        elif key == "spec" and isinstance(value, dict):
            base["spec"].update(value)
        else:
            base[key] = value
    return base


def test_agent_manifest_validates_minimal_dict() -> None:
    """Valid minimal manifest parses successfully."""
    manifest = AgentManifest.model_validate(_minimal_manifest_dict())

    assert manifest.metadata.name == "test-agent"
    assert manifest.spec.instructions.system == "SYSTEM.md"
    assert manifest.api_version == "antigravity-agentkit.dev/v1alpha1"


def test_agent_manifest_from_hello_agent_example(hello_world_agent_dir: Path) -> None:
    """hello-agent example manifest validates via loader."""
    manifest, _ = load_agent_yaml(hello_world_agent_dir / "agent.yaml")

    assert manifest.kind == "Agent"
    assert manifest.metadata.name == "hello-world"


@pytest.mark.parametrize(
    "bad_api_version",
    [
        "v1",
        "antigravity-agentkit.dev/v2",
        "kubernetes/v1",
    ],
)
def test_agent_manifest_rejects_bad_api_version(bad_api_version: str) -> None:
    """Invalid apiVersion values are rejected."""
    data = _minimal_manifest_dict(apiVersion=bad_api_version)

    with pytest.raises(ValidationError):
        AgentManifest.model_validate(data)


@pytest.mark.parametrize(
    "bad_name",
    [
        "Hello-Agent",
        "hello_agent",
        "1hello",
        "-hello",
        "",
        "a" * 65,
    ],
)
def test_agent_manifest_rejects_bad_names(bad_name: str) -> None:
    """Agent names must be lowercase hyphenated identifiers."""
    data = _minimal_manifest_dict(metadata={"name": bad_name})

    with pytest.raises(ValidationError):
        AgentManifest.model_validate(data)


def test_agent_manifest_rejects_unknown_top_level_fields() -> None:
    """extra='forbid' rejects unknown manifest keys."""
    data = _minimal_manifest_dict()
    data["unknownField"] = True

    with pytest.raises(ValidationError):
        AgentManifest.model_validate(data)


def test_agent_manifest_rejects_unknown_metadata_fields() -> None:
    """extra='forbid' rejects unknown metadata keys."""
    data = _minimal_manifest_dict()
    data["metadata"]["team"] = "platform"

    with pytest.raises(ValidationError):
        AgentManifest.model_validate(data)


def test_vertex_requires_project_when_enabled() -> None:
    """vertex.enabled=true requires vertex.project."""
    data = _minimal_manifest_dict(
        spec={
            "instructions": {"system": "SYSTEM.md"},
            "runtime": {
                "framework": "antigravity",
                "vertex": {"enabled": True},
            },
        }
    )

    with pytest.raises(ValidationError, match="vertex.project"):
        AgentManifest.model_validate(data)


def test_subagent_markdown_requires_file() -> None:
    """Markdown subagents must declare a file path."""
    data = _minimal_manifest_dict(
        spec={
            "instructions": {"system": "SYSTEM.md"},
            "subagents": [{"name": "reviewer", "type": "markdown"}],
        }
    )

    with pytest.raises(ValidationError, match="file"):
        AgentManifest.model_validate(data)


def test_capabilities_enabled_tools_validate() -> None:
    """Capabilities enabledTools accepts builtin tool names."""
    data = _minimal_manifest_dict(
        spec={
            "instructions": {"system": "SYSTEM.md"},
            "runtime": {
                "framework": "antigravity",
                "capabilities": {
                    "mode": "restricted",
                    "enabledTools": ["search_web", "view_file"],
                },
            },
        }
    )

    manifest = AgentManifest.model_validate(data)

    assert manifest.spec.runtime.capabilities.enabled_tools == ["search_web", "view_file"]
