"""Tests for agent directory loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from antigravity_agentkit.exceptions import LoadError
from antigravity_agentkit.loader import load_agent_directory, load_agent_yaml, load_system_md


def _write_asset_reference_agent(agent_dir: Path, asset: str, reference: str) -> None:
    """Write a minimal agent manifest referencing one external asset."""
    spec: dict[str, object] = {"instructions": {"system": "SYSTEM.md"}}
    if asset == "system":
        spec["instructions"] = {"system": reference}
    elif asset == "mcp":
        spec["mcp"] = {"file": reference}
    elif asset == "policies":
        spec["policies"] = {"file": reference}
    elif asset == "eval":
        spec["evals"] = {"files": [reference]}
    elif asset == "skill":
        spec["skills"] = {"local": [reference]}
    else:
        spec["subagents"] = [{"name": "reviewer", "file": reference}]

    manifest = {
        "apiVersion": "antigravity-agentkit.dev/v1alpha1",
        "kind": "Agent",
        "metadata": {"name": "test-agent"},
        "spec": spec,
    }
    (agent_dir / "agent.yaml").write_text(json.dumps(manifest), encoding="utf-8")


def _write_external_asset(tmp_path: Path, asset: str) -> Path:
    """Create a valid external asset for path-containment tests."""
    if asset == "skill":
        asset_path = tmp_path / "external-skill"
        asset_path.mkdir()
        (asset_path / "SKILL.md").write_text(
            "---\nname: external\ndescription: External skill.\n---\n\n# External\n",
            encoding="utf-8",
        )
        return asset_path

    asset_path = tmp_path / f"external-{asset}"
    content = {
        "system": "# External\n",
        "mcp": '{"mcpServers": {}}',
        "policies": "default: allow\n",
        "eval": "version: 1\ncases: []\n",
        "subagent": "---\nname: reviewer\ndescription: Reviews.\n---\n\n# Reviewer\n",
    }[asset]
    asset_path.write_text(content, encoding="utf-8")
    return asset_path


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


@pytest.mark.parametrize("asset", ["system", "mcp", "policies", "eval", "skill", "subagent"])
@pytest.mark.parametrize("path_kind", ["absolute", "traversal"])
def test_load_agent_rejects_asset_paths_outside_root(
    tmp_path: Path,
    asset: str,
    path_kind: str,
) -> None:
    """Every manifest-controlled asset path must remain inside the agent root."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "SYSTEM.md").write_text("# Agent\n", encoding="utf-8")
    external_asset = _write_external_asset(tmp_path, asset)
    reference = str(external_asset) if path_kind == "absolute" else f"../{external_asset.name}"
    _write_asset_reference_agent(agent_dir, asset, reference)

    with pytest.raises(LoadError, match="must be relative|escapes the agent directory"):
        load_agent_directory(agent_dir)


@pytest.mark.parametrize(
    ("section", "filename", "error"),
    [
        ("mcp", "missing.json", "MCP config not found"),
        ("policies", "missing.yaml", "Policies file not found"),
    ],
)
def test_load_agent_rejects_missing_declared_files(
    tmp_path: Path,
    section: str,
    filename: str,
    error: str,
) -> None:
    """Declared MCP and policy files are required rather than silently omitted."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "SYSTEM.md").write_text("# Agent\n", encoding="utf-8")
    _write_asset_reference_agent(agent_dir, section, filename)

    with pytest.raises(LoadError, match=error):
        load_agent_directory(agent_dir)
