"""Tests for deployable source package building."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from antigravity_agentkit.deploy import build_source_package
from antigravity_agentkit.exceptions import DeployError, LoadError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.tests.deploy.conftest import write_minimal_agent


def test_build_source_package_writes_expected_files(ship_project: AgentProject) -> None:
    """Package build emits runtime entrypoint and metadata."""
    package_dir = build_source_package(ship_project)

    assert (package_dir / "agent.py").is_file()
    assert (package_dir / "requirements.txt").is_file()
    assert (package_dir / "metadata.json").is_file()
    assert (package_dir / "agent.yaml").is_file()
    assert (package_dir / "policies.yaml").is_file()
    assert (package_dir / "compiled-agent-ir.json").is_file()
    assert (package_dir / "agentkit.lock.json").is_file()
    assert "create_agent_from_ir_file" in (package_dir / "agent.py").read_text(encoding="utf-8")


def test_build_source_package_metadata_json_shape(ship_project: AgentProject) -> None:
    """metadata.json records agent identity and compiled summary fields."""
    package_dir = build_source_package(ship_project)
    metadata = json.loads((package_dir / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["agentName"] == "ship-agent"
    assert "compiled" in metadata
    assert "vertexEnabled" in metadata["compiled"]
    assert "mcpServers" in metadata["compiled"]
    assert "toolCount" in metadata["compiled"]
    assert "policyCount" in metadata["compiled"]
    assert isinstance(metadata["compiled"]["toolCount"], int)
    assert isinstance(metadata["compiled"]["policyCount"], int)


def test_build_source_package_rejects_unsafe_output_paths(tmp_path: Path) -> None:
    """Package output cannot delete the project, an ancestor, or source directories."""
    agent_dir = tmp_path / "agent"
    project = write_minimal_agent(agent_dir)
    source_dir = agent_dir / "assets"
    source_dir.mkdir()
    sentinel = source_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    for output_dir in (agent_dir, tmp_path, source_dir):
        with pytest.raises(DeployError, match="Package output"):
            build_source_package(project, output_dir=output_dir)
        assert sentinel.read_text(encoding="utf-8") == "keep"


def test_build_source_package_supports_external_output(tmp_path: Path) -> None:
    """A package may be written outside the agent project."""
    project = write_minimal_agent(tmp_path / "agent")

    package_dir = build_source_package(project, output_dir=tmp_path / "package")

    assert package_dir == (tmp_path / "package").resolve()
    assert (package_dir / "agent.py").is_file()


def test_build_source_package_copies_nested_manifest_files(tmp_path: Path) -> None:
    """Nested system, MCP, and policy paths retain their package layout."""
    agent_dir = tmp_path / "agent"
    write_minimal_agent(agent_dir, "config/SYSTEM.md")
    (agent_dir / "config" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"clock": {"command": "python3"}}}),
        encoding="utf-8",
    )
    (agent_dir / "config" / "policies.yaml").write_text(
        "default: allow\n",
        encoding="utf-8",
    )
    manifest_path = agent_dir / "agent.yaml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8")
        + "\n  mcp:\n    file: config/mcp.json\n"
        + "  policies:\n    file: config/policies.yaml\n",
        encoding="utf-8",
    )
    project = AgentProject.load(agent_dir)

    package_dir = build_source_package(project, output_dir=tmp_path / "package")

    assert (package_dir / "config" / "SYSTEM.md").is_file()
    assert (package_dir / "config" / "mcp.json").is_file()
    assert (package_dir / "config" / "policies.yaml").is_file()


@pytest.mark.parametrize("path_kind", ["traversal", "absolute"])
def test_build_source_package_rejects_escaping_source_paths(
    tmp_path: Path,
    path_kind: str,
) -> None:
    """Package file references must remain relative to the agent directory."""
    agent_dir = tmp_path / "agent"
    external_system = tmp_path / "external-SYSTEM.md"
    external_system.write_text("# Agent\n", encoding="utf-8")
    system_path = str(external_system) if path_kind == "absolute" else "../external-SYSTEM.md"
    write_minimal_agent(agent_dir)
    manifest_path = agent_dir / "agent.yaml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace("SYSTEM.md", system_path),
        encoding="utf-8",
    )
    with pytest.raises(LoadError, match="must be relative|escapes the agent directory"):
        AgentProject.load(agent_dir)


def test_build_source_package_is_self_contained(repo_root: Path, tmp_path: Path) -> None:
    """The Agent Platform example package retains eval and local MCP assets."""
    project = AgentProject.load(repo_root / "examples" / "agent_platform")

    package_dir = build_source_package(project, output_dir=tmp_path / "package")
    packaged_project = AgentProject.load(package_dir)

    assert (package_dir / "evals" / "smoke.yaml").is_file()
    assert (package_dir / "server" / "clock_mcp.py").is_file()
    assert len(packaged_project.data.evals) == 1
    assert "clock" in (packaged_project.data.mcp_config or {}).get("mcpServers", {})


def test_build_source_package_keeps_assets_and_discovered_components(tmp_path: Path) -> None:
    """Root copying retains arbitrary assets and conventionally discovered components."""
    agent_dir = tmp_path / "agent"
    write_minimal_agent(agent_dir)
    (agent_dir / "assets").mkdir()
    (agent_dir / "assets" / "prompt.txt").write_text("runtime asset", encoding="utf-8")
    (agent_dir / "skills" / "helper").mkdir(parents=True)
    (agent_dir / "skills" / "helper" / "SKILL.md").write_text(
        "---\nname: helper\ndescription: Helps.\n---\n\n# Helper\n",
        encoding="utf-8",
    )
    (agent_dir / "subagents").mkdir()
    (agent_dir / "subagents" / "reviewer.md").write_text(
        "---\nname: reviewer\ndescription: Reviews.\n---\n\n# Reviewer\n",
        encoding="utf-8",
    )
    project = AgentProject.load(agent_dir)

    package_dir = build_source_package(project, output_dir=tmp_path / "package")
    packaged_project = AgentProject.load(package_dir)

    assert (package_dir / "assets" / "prompt.txt").read_text(encoding="utf-8") == "runtime asset"
    assert "helper" in packaged_project.data.skills
    assert "reviewer" in packaged_project.data.subagents


def test_build_source_package_excludes_dev_and_secret_files(tmp_path: Path) -> None:
    """Build, environment, virtualenv, cache, and bytecode files are not packaged."""
    agent_dir = tmp_path / "agent"
    project = write_minimal_agent(agent_dir)
    (agent_dir / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (agent_dir / ".venv" / "bin").mkdir(parents=True)
    (agent_dir / ".venv" / "bin" / "python").write_text("binary", encoding="utf-8")
    (agent_dir / "module.pyc").write_bytes(b"bytecode")

    package_dir = build_source_package(project, output_dir=tmp_path / "package")

    assert not (package_dir / ".env").exists()
    assert not (package_dir / ".venv").exists()
    assert not (package_dir / "module.pyc").exists()


def test_build_source_package_excludes_build_and_git_dirs(tmp_path: Path) -> None:
    """Development directories such as .build and .git are not packaged."""
    agent_dir = tmp_path / "agent"
    project = write_minimal_agent(agent_dir)
    (agent_dir / ".build" / "stale").mkdir(parents=True)
    (agent_dir / ".build" / "stale" / "artifact.txt").write_text("stale", encoding="utf-8")
    (agent_dir / ".git" / "config").parent.mkdir(parents=True)
    (agent_dir / ".git" / "config").write_text("[core]\n", encoding="utf-8")

    package_dir = build_source_package(project, output_dir=tmp_path / "package")

    assert not (package_dir / ".build").exists()
    assert not (package_dir / ".git").exists()


def test_build_source_package_rejects_symlinks(tmp_path: Path) -> None:
    """Source package traversal rejects symlinks instead of following them."""
    agent_dir = tmp_path / "agent"
    project = write_minimal_agent(agent_dir)
    external = tmp_path / "secret.txt"
    external.write_text("secret", encoding="utf-8")
    (agent_dir / "linked-secret.txt").symlink_to(external)

    with pytest.raises(DeployError, match="Symlinks are not allowed"):
        build_source_package(project, output_dir=tmp_path / "package")
