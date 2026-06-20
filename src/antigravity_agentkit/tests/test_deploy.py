"""Tests for deploy module and ship workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_agentkit.deploy import (
    build_deployment_config,
    build_source_package,
    deploy,
    load_deployment,
)
from antigravity_agentkit.exceptions import DeployError, LoadError
from antigravity_agentkit.project import AgentProject


def test_load_deployment_parses_ship_fixture(ship_agent_dir: Path) -> None:
    """ship_agent fixture deployment.yaml loads successfully."""
    deployment = load_deployment(ship_agent_dir)

    assert deployment.metadata.name == "ship-agent"
    assert deployment.spec.target == "agent-platform"


def test_load_deployment_raises_when_missing(tmp_path: Path) -> None:
    """Ship helpers error when deployment.yaml is absent."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "SYSTEM.md").write_text("# Agent\n", encoding="utf-8")
    (agent_dir / "agent.yaml").write_text(
        "\n".join(
            [
                "apiVersion: antigravity-agentkit.dev/v1alpha1",
                "kind: Agent",
                "metadata:",
                "  name: test-agent",
                "spec:",
                "  instructions:",
                "    system: SYSTEM.md",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(LoadError, match="Deployment manifest not found"):
        load_deployment(agent_dir)


def test_build_source_package_writes_expected_files(ship_agent_dir: Path) -> None:
    """Package build emits runtime entrypoint and metadata."""
    project = AgentProject.load(ship_agent_dir)
    package_dir = build_source_package(project)

    assert (package_dir / "agent.py").is_file()
    assert (package_dir / "requirements.txt").is_file()
    assert (package_dir / "metadata.json").is_file()
    assert (package_dir / "agent.yaml").is_file()
    assert (package_dir / "requirements.txt").read_text(encoding="utf-8") == (
        "antigravity-agentkit[antigravity]\n"
    )


def test_build_deployment_config_uses_deployment_manifest(ship_agent_dir: Path) -> None:
    """Deployment config reads scaling from deployment.yaml."""
    project = AgentProject.load(ship_agent_dir)
    deployment = load_deployment(ship_agent_dir)
    config = build_deployment_config(project, deployment, "test-project", "us-central1")

    assert config["project"] == "test-project"
    assert config["location"] == "us-central1"
    assert config["target"] == "agent-platform"
    assert config["min_instances"] == 0
    assert config["max_instances"] == 1
    assert config["display_name"] == "Ship Agent"


def test_deploy_dry_run_writes_config(ship_agent_dir: Path, tmp_path: Path) -> None:
    """Dry-run deploy writes deployment-config.json without GCP credentials."""
    project = AgentProject.load(ship_agent_dir)
    deployment = load_deployment(ship_agent_dir)
    out = tmp_path / "deployment-config.json"

    summary = deploy(
        project,
        deployment,
        "test-project",
        "us-central1",
        output_path=out,
        dry_run=True,
    )

    assert summary["status"] == "dry_run"
    assert Path(summary["config_path"]).is_file()
    assert summary["config"]["target"] == "agent-platform"


def test_unimplemented_target_raises(ship_agent_dir: Path) -> None:
    """Non-agent-platform targets raise DeployError in M1."""
    project = AgentProject.load(ship_agent_dir)
    deployment = load_deployment(ship_agent_dir)
    gemini_deployment = deployment.model_copy(
        update={"spec": deployment.spec.model_copy(update={"target": "gemini-api"})}
    )

    with pytest.raises(DeployError, match="not implemented"):
        build_deployment_config(project, gemini_deployment, "test-project", "us-central1")
