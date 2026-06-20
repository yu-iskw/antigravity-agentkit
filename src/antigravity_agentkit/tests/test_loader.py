"""Tests for agent directory loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_agentkit.exceptions import LoadError
from antigravity_agentkit.loader import load_agent_directory, load_agent_yaml, load_system_md


def test_load_hello_agent(hello_world_agent_dir: Path) -> None:
    """Load minimal hello-agent example."""
    data = load_agent_directory(hello_world_agent_dir)

    assert data.root == hello_world_agent_dir.resolve()
    assert data.manifest.metadata.name == "hello-world"
    assert data.manifest.metadata.display_name == "Hello World"
    assert "helpful" in data.system_instructions.lower()
    assert data.mcp_config is None
    assert data.policies is None
    assert not data.skills
    assert not data.subagents
    assert not data.evals


def test_load_mcp_example(mcp_agent_dir: Path) -> None:
    """Load mcp example with MCP, skills, subagents, policies, and evals."""
    data = load_agent_directory(mcp_agent_dir)

    assert data.manifest.metadata.name == "mcp-demo"
    assert data.manifest.metadata.labels["domain"] == "examples"
    assert data.mcp_config is not None
    assert "clock" in data.mcp_config.get("mcpServers", {})
    assert data.policies is not None
    assert data.policies.get("default") == "deny"
    assert "mcp-guide" in data.skills
    assert data.skills["mcp-guide"].description
    assert "time-checker" in data.subagents
    assert len(data.evals) == 1
    assert data.evals[0]["suite"]["version"] == 1


def test_load_agent_yaml_returns_raw_manifest(hello_world_agent_dir: Path) -> None:
    """load_agent_yaml returns both parsed manifest and raw dict."""
    manifest, raw = load_agent_yaml(hello_world_agent_dir / "agent.yaml")

    assert manifest.metadata.name == "hello-world"
    assert raw["kind"] == "Agent"
    assert raw["apiVersion"] == "antigravity-agentkit.dev/v1alpha1"


def test_load_system_md(hello_world_agent_dir: Path) -> None:
    """load_system_md reads SYSTEM.md content."""
    content = load_system_md(hello_world_agent_dir / "SYSTEM.md")

    assert content.startswith("#")


def test_load_agent_directory_missing_raises(tmp_path: Path) -> None:
    """Missing agent directory raises LoadError."""
    with pytest.raises(LoadError, match="Agent directory not found"):
        load_agent_directory(tmp_path / "nonexistent-agent")


def test_load_agent_yaml_missing_raises(tmp_path: Path) -> None:
    """Missing agent.yaml raises LoadError."""
    with pytest.raises(LoadError, match="Agent manifest not found"):
        load_agent_yaml(tmp_path / "agent.yaml")
