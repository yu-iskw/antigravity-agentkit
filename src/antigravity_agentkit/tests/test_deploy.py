"""Tests for deploy module and ship workflow."""

from __future__ import annotations

import json
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
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.tests.constants import TEST_GCP_LOCATION, TEST_GCP_PROJECT


def test_load_deployment_parses_ship_fixture(ship_deployment: DeploymentManifest) -> None:
    """ship_agent fixture deployment.yaml loads successfully."""
    assert ship_deployment.metadata.name == "ship-agent"
    assert ship_deployment.spec.target == "agent-platform"
    assert ship_deployment.spec.service_account == "ship-agent@test-project.iam.gserviceaccount.com"
    assert ship_deployment.spec.gateway is not None
    assert ship_deployment.spec.gateway.enabled is True


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


def test_build_source_package_writes_expected_files(ship_project: AgentProject) -> None:
    """Package build emits runtime entrypoint and metadata."""
    package_dir = build_source_package(ship_project)

    assert (package_dir / "agent.py").is_file()
    assert (package_dir / "requirements.txt").is_file()
    assert (package_dir / "metadata.json").is_file()
    assert (package_dir / "agent.yaml").is_file()
    assert (package_dir / "policies.yaml").is_file()
    assert (package_dir / "requirements.txt").read_text(encoding="utf-8") == (
        "antigravity-agentkit[antigravity]\n"
    )


def test_build_deployment_config_includes_scaling_gateway_and_identity(
    ship_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """Deployment config maps scaling, gateway, and service account from deployment.yaml."""
    project, deployment = ship_context
    config = build_deployment_config(project, deployment, TEST_GCP_PROJECT, TEST_GCP_LOCATION)

    assert config["project"] == TEST_GCP_PROJECT
    assert config["location"] == TEST_GCP_LOCATION
    assert config["target"] == "agent-platform"
    assert config["min_instances"] == 0
    assert config["max_instances"] == 1
    assert config["container_concurrency"] == deployment.spec.container_concurrency
    assert config["display_name"] == "Ship Agent"
    assert config["service_account"] == deployment.spec.service_account
    assert config["resource_limits"] == {"cpu": "1", "memory": "512Mi"}
    assert config["labels"]["env"] == "test"
    assert config["labels"]["managed-by"] == "antigravity-agentkit"
    assert config["labels"]["agent-name"] == "ship-agent"
    assert config["gateway"] == {
        "enabled": True,
        "egressPolicy": "restricted",
        "requiredEndpoints": ["https://example.googleapis.com"],
    }
    assert config["entrypoint_module"] == "agent"
    assert config["entrypoint_object"] == "root_agent"
    assert config["requirements_file"] == "requirements.txt"


def test_deploy_dry_run_writes_config(
    ship_context: tuple[AgentProject, DeploymentManifest],
    tmp_path: Path,
) -> None:
    """Dry-run deploy writes deployment-config.json without GCP credentials."""
    project, deployment = ship_context
    out = tmp_path / "deployment-config.json"

    summary = deploy(
        project,
        deployment,
        TEST_GCP_PROJECT,
        TEST_GCP_LOCATION,
        output_path=out,
        dry_run=True,
    )

    assert summary["status"] == "dry_run"
    assert Path(summary["config_path"]).is_file()
    assert summary["config"]["target"] == "agent-platform"
    assert Path(summary["package_dir"]).is_dir()

    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["source_packages"] == [summary["config"]["source_packages"][0]]
    assert written["gateway"]["enabled"] is True


def test_deploy_live_raises_not_implemented(
    ship_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """Live deploy always raises until Agent Runtime apply is implemented."""
    project, deployment = ship_context

    with pytest.raises(DeployError, match="not implemented"):
        deploy(
            project,
            deployment,
            TEST_GCP_PROJECT,
            TEST_GCP_LOCATION,
            dry_run=False,
        )


def test_unimplemented_target_raises(
    ship_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """Non-agent-platform targets raise DeployError in M1."""
    project, deployment = ship_context
    gemini_deployment = deployment.model_copy(
        update={"spec": deployment.spec.model_copy(update={"target": "gemini-api"})}
    )

    with pytest.raises(DeployError, match="not implemented"):
        build_deployment_config(project, gemini_deployment, TEST_GCP_PROJECT, TEST_GCP_LOCATION)
