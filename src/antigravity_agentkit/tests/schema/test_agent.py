"""Tests for agent.yaml schema models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from antigravity_agentkit.loader import load_agent_yaml
from antigravity_agentkit.schema.agent import AgentManifest
from antigravity_agentkit.tests.schema.conftest import minimal_manifest_dict


def test_agent_manifest_validates_minimal_dict() -> None:
    """Valid minimal manifest parses successfully."""
    manifest = AgentManifest.model_validate(minimal_manifest_dict())

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
    data = minimal_manifest_dict(apiVersion=bad_api_version)

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
    data = minimal_manifest_dict(metadata={"name": bad_name})

    with pytest.raises(ValidationError):
        AgentManifest.model_validate(data)


def test_agent_manifest_rejects_unknown_top_level_fields() -> None:
    """extra='forbid' rejects unknown manifest keys."""
    data = minimal_manifest_dict()
    data["unknownField"] = True

    with pytest.raises(ValidationError):
        AgentManifest.model_validate(data)


def test_agent_manifest_rejects_unknown_metadata_fields() -> None:
    """extra='forbid' rejects unknown metadata keys."""
    data = minimal_manifest_dict()
    data["metadata"]["team"] = "platform"

    with pytest.raises(ValidationError):
        AgentManifest.model_validate(data)


def test_vertex_requires_project_when_enabled() -> None:
    """vertex.enabled=true requires vertex.project."""
    data = minimal_manifest_dict(
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
    data = minimal_manifest_dict(
        spec={
            "instructions": {"system": "SYSTEM.md"},
            "subagents": [{"name": "reviewer", "type": "markdown"}],
        }
    )

    with pytest.raises(ValidationError, match="file"):
        AgentManifest.model_validate(data)


def test_subagent_remote_requires_registry_ref() -> None:
    """Remote subagents must declare a registryRef."""
    data = minimal_manifest_dict(
        spec={
            "instructions": {"system": "SYSTEM.md"},
            "subagents": [{"name": "remote-helper", "type": "remote"}],
        }
    )

    with pytest.raises(ValidationError, match="registryRef"):
        AgentManifest.model_validate(data)


def test_subagent_duplicate_names_rejected() -> None:
    """Duplicate subagent names within a manifest are rejected."""
    data = minimal_manifest_dict(
        spec={
            "instructions": {"system": "SYSTEM.md"},
            "subagents": [
                {"name": "reviewer", "type": "markdown", "file": "subagents/a.md"},
                {"name": "reviewer", "type": "markdown", "file": "subagents/b.md"},
            ],
        }
    )

    with pytest.raises(ValidationError, match="Duplicate subagent name"):
        AgentManifest.model_validate(data)


def test_capabilities_enabled_tools_validate() -> None:
    """Capabilities enabledTools accepts builtin tool names."""
    data = minimal_manifest_dict(
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


def test_model_dump_agent_yaml_round_trip() -> None:
    """model_dump_agent_yaml preserves camelCase aliases."""
    manifest = AgentManifest.model_validate(minimal_manifest_dict())
    dumped = manifest.model_dump_agent_yaml()

    assert dumped["apiVersion"] == "antigravity-agentkit.dev/v1alpha1"
    assert dumped["metadata"]["displayName"] == "Test Agent"
    assert "display_name" not in dumped["metadata"]
