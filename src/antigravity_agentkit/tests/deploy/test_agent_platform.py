"""Tests for Agent Platform deployment adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from antigravity_agentkit.deploy import build_deployment_config, deploy
from antigravity_agentkit.deploy._common import has_gcp_credentials
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.tests.constants import TEST_GCP_LOCATION, TEST_GCP_PROJECT
from antigravity_agentkit.tests.deploy.conftest import write_minimal_agent


def test_build_deployment_config_includes_scaling_gateway_and_identity(
    ship_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """Deployment config maps scaling, gateway, and service account from deployment.yaml."""
    project, deployment = ship_context
    config = build_deployment_config(project, deployment, TEST_GCP_PROJECT, TEST_GCP_LOCATION)

    assert config["project"] == TEST_GCP_PROJECT
    assert config["location"] == TEST_GCP_LOCATION
    assert config["target"] == "agent-platform-runtime"
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


def test_build_deployment_config_includes_vertex_when_enabled(tmp_path: Path) -> None:
    """Vertex settings are included when enabled in the agent manifest."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "SYSTEM.md").write_text("# Agent\n", encoding="utf-8")
    (agent_dir / "agent.yaml").write_text(
        "\n".join(
            [
                "apiVersion: antigravity-agentkit.dev/v1alpha1",
                "kind: Agent",
                "metadata:",
                "  name: vertex-agent",
                "spec:",
                "  instructions:",
                "    system: SYSTEM.md",
                "  runtime:",
                "    framework: antigravity",
                "    vertex:",
                "      enabled: true",
                "      project: manifest-project",
                "      location: us-west1",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "deployment.yaml").write_text(
        "\n".join(
            [
                "apiVersion: antigravity-agentkit.dev/v1alpha1",
                "kind: Deployment",
                "metadata:",
                "  name: vertex-agent",
                "spec:",
                "  target: agent-platform",
            ]
        ),
        encoding="utf-8",
    )
    project = AgentProject.load(agent_dir)
    deployment = DeploymentManifest.model_validate(
        yaml.safe_load((agent_dir / "deployment.yaml").read_text(encoding="utf-8"))
    )

    config = build_deployment_config(project, deployment, TEST_GCP_PROJECT, TEST_GCP_LOCATION)

    assert config["vertex"] == {
        "project": "manifest-project",
        "location": "us-west1",
    }


def test_build_deployment_config_display_name_override(
    ship_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """deployment.yaml displayName overrides the agent manifest display name."""
    project, deployment = ship_context
    overridden = deployment.model_copy(
        update={"spec": deployment.spec.model_copy(update={"display_name": "Override Name"})}
    )

    config = build_deployment_config(project, overridden, TEST_GCP_PROJECT, TEST_GCP_LOCATION)

    assert config["display_name"] == "Override Name"


def test_build_deployment_config_preserves_reserved_labels(
    ship_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """User labels cannot override AgentKit deployment identity labels."""
    project, deployment = ship_context
    project.manifest.metadata.labels.update(
        {"managed-by": "manifest", "agent-name": "manifest", "shared": "manifest"}
    )
    overridden = deployment.model_copy(
        update={
            "spec": deployment.spec.model_copy(
                update={
                    "labels": {
                        **deployment.spec.labels,
                        "managed-by": "deployment",
                        "agent-name": "deployment",
                        "shared": "deployment",
                    }
                }
            )
        }
    )

    config = build_deployment_config(project, overridden, TEST_GCP_PROJECT, TEST_GCP_LOCATION)

    assert config["labels"]["managed-by"] == "antigravity-agentkit"
    assert config["labels"]["agent-name"] == "ship-agent"
    assert config["labels"]["shared"] == "deployment"


def test_build_deployment_config_omits_optional_fields(tmp_path: Path) -> None:
    """Minimal deployment spec omits optional scaling and gateway keys."""
    project = write_minimal_agent(tmp_path / "agent")
    deployment = DeploymentManifest.model_validate(
        {
            "apiVersion": "antigravity-agentkit.dev/v1alpha1",
            "kind": "Deployment",
            "metadata": {"name": "test-agent"},
            "spec": {"target": "agent-platform"},
        }
    )

    config = build_deployment_config(project, deployment, TEST_GCP_PROJECT, TEST_GCP_LOCATION)

    assert "gateway" not in config
    assert "resource_limits" not in config
    assert "min_instances" not in config
    assert "max_instances" not in config
    assert "service_account" not in config


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
    assert summary["config"]["target"] == "agent-platform-runtime"
    assert Path(summary["package_dir"]).is_dir()

    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["source_packages"] == [summary["config"]["source_packages"][0]]
    assert written["gateway"]["enabled"] is True


def test_has_gcp_credentials_with_application_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GOOGLE_APPLICATION_CREDENTIALS counts as configured credentials."""
    creds_file = tmp_path / "creds.json"
    creds_file.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("CLOUDSDK_AUTH_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds_file))

    assert has_gcp_credentials()


def test_deploy_implicit_dry_run_without_credentials(
    ship_context: tuple[AgentProject, DeploymentManifest],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """deploy() defaults to dry-run when credential env vars are unset and ADC is absent."""
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("CLOUDSDK_AUTH_ACCESS_TOKEN", raising=False)
    if has_gcp_credentials():
        pytest.skip("ADC present locally; implicit dry-run path requires absent credentials")

    project, deployment = ship_context
    out = tmp_path / "deployment-config.json"

    summary = deploy(
        project,
        deployment,
        TEST_GCP_PROJECT,
        TEST_GCP_LOCATION,
        output_path=out,
        dry_run=None,
    )

    assert summary["status"] == "dry_run"


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
