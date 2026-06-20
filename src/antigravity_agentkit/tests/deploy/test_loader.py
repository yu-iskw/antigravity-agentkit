"""Tests for deployment manifest loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_agentkit.deploy import load_deployment
from antigravity_agentkit.exceptions import LoadError
from antigravity_agentkit.schema.deployment import DeploymentManifest


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
