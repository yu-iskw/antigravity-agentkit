"""Shared fixtures for deploy module tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest


def write_minimal_agent(agent_dir: Path, system_path: str = "SYSTEM.md") -> AgentProject:
    """Create and load a minimal agent project for packaging tests."""
    agent_dir.mkdir()
    system_file = agent_dir / system_path
    system_file.parent.mkdir(parents=True, exist_ok=True)
    system_file.write_text("# Agent\n", encoding="utf-8")
    (agent_dir / "agent.yaml").write_text(
        "\n".join(
            [
                "apiVersion: antigravity-agentkit.dev/v1alpha1",
                "kind: Agent",
                "metadata:",
                "  name: test-agent",
                "spec:",
                "  instructions:",
                f"    system: {system_path}",
            ]
        ),
        encoding="utf-8",
    )
    return AgentProject.load(agent_dir)


@pytest.fixture
def gemini_deploy_context(tmp_path: Path) -> tuple[AgentProject, DeploymentManifest]:
    """Agent project configured for gemini-api deployment."""
    project = write_minimal_agent(tmp_path / "agent")
    deployment = DeploymentManifest.model_validate(
        {
            "apiVersion": "antigravity-agentkit.dev/v1alpha1",
            "kind": "Deployment",
            "metadata": {"name": "test-agent"},
            "spec": {
                "target": "gemini-api",
                "displayName": "Gemini Demo",
                "labels": {"env": "test"},
            },
        }
    )
    return project, deployment
