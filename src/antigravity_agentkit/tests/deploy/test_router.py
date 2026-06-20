"""Tests for deploy target routing."""

from __future__ import annotations

import pytest

from antigravity_agentkit.deploy import build_deployment_config
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.tests.constants import TEST_GCP_LOCATION, TEST_GCP_PROJECT


def test_router_builds_agent_platform_target(
    ship_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """Agent Platform configuration builds through the router."""
    project, deployment = ship_context

    config = build_deployment_config(
        project,
        deployment,
        TEST_GCP_PROJECT,
        TEST_GCP_LOCATION,
    )

    assert config["target"] == "agent-platform-runtime"


def test_router_builds_gemini_api_target(
    gemini_deploy_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """Gemini API configuration builds through the router."""
    project, deployment = gemini_deploy_context

    config = build_deployment_config(
        project,
        deployment,
        TEST_GCP_PROJECT,
        TEST_GCP_LOCATION,
    )

    assert config["base_agent"] == "antigravity-preview-05-2026"


@pytest.mark.parametrize("target", ["ai-studio", "cloud-run"])
def test_router_rejects_unsupported_targets(
    ship_context: tuple[AgentProject, DeploymentManifest],
    target: str,
) -> None:
    """Unsupported deploy targets raise DeployError from the router."""
    project, deployment = ship_context
    routed = deployment.model_copy(
        update={"spec": deployment.spec.model_copy(update={"target": target})}
    )

    with pytest.raises(DeployError, match="not implemented"):
        build_deployment_config(project, routed, TEST_GCP_PROJECT, TEST_GCP_LOCATION)
