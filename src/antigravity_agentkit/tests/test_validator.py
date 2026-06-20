"""Tests for project validation levels and profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from antigravity_agentkit.exceptions import LoadError, ValidationError
from antigravity_agentkit.loader import load_agent_directory
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.agent import McpAdmissionPolicy
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.validator import (
    assert_valid_project,
    validate_deployment,
    validate_project,
)


def test_hello_agent_passes_schema_validation(hello_world_agent_dir: Path) -> None:
    """Minimal hello-agent passes schema-level validation."""
    project = AgentProject.load(hello_world_agent_dir)
    collector = validate_project(project.root, project.data, level="schema", profile="dev-open")

    assert not collector.has_errors()


def test_bigquery_agent_passes_full_dev_open(mcp_agent_dir: Path) -> None:
    """mcp example passes full validation under dev-open profile."""
    project = AgentProject.load(mcp_agent_dir)
    collector = validate_project(project.root, project.data, level="full", profile="dev-open")

    assert not collector.has_errors()


@pytest.mark.parametrize("level", ["syntax", "schema", "security", "cloud", "full"])
def test_validation_levels_include_prior_checks(
    mcp_agent_dir: Path,
    level: Literal["syntax", "schema", "security", "cloud", "full"],
) -> None:
    """Higher validation levels include lower-level checks without new errors."""
    project = AgentProject.load(mcp_agent_dir)
    collector = validate_project(
        project.root,
        project.data,
        level=level,
        profile="dev-open",
    )

    assert not collector.has_errors()


def test_load_raises_for_invalid_mcp_json(tmp_path: Path) -> None:
    """Loading an agent with invalid mcp.json raises LoadError."""
    agent_dir = tmp_path / "broken-agent"
    agent_dir.mkdir()
    (agent_dir / "SYSTEM.md").write_text("# Agent\n", encoding="utf-8")
    (agent_dir / "agent.yaml").write_text(
        "\n".join(
            [
                "apiVersion: antigravity-agentkit.dev/v1alpha1",
                "kind: Agent",
                "metadata:",
                "  name: broken-agent",
                "spec:",
                "  instructions:",
                "    system: SYSTEM.md",
                "  mcp:",
                "    file: mcp.json",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "mcp.json").write_text("{ not valid json", encoding="utf-8")

    with pytest.raises(LoadError, match="Invalid JSON"):
        load_agent_directory(agent_dir)


def test_prod_readonly_requires_deployment_file(mcp_agent_dir: Path) -> None:
    """prod-readonly at cloud level requires deployment.yaml when absent."""
    project = AgentProject.load(mcp_agent_dir)
    collector = validate_project(project.root, project.data, level="cloud", profile="prod-readonly")

    assert collector.has_errors()
    assert any(d.code == "AGK-DEPLOY-003" for d in collector.errors())


def test_prod_readonly_requires_service_account(
    ship_deployment: DeploymentManifest, ship_project: AgentProject
) -> None:
    """prod-readonly profile requires deployment.serviceAccount when deployment.yaml exists."""
    deployment = ship_deployment.model_copy(
        update={"spec": ship_deployment.spec.model_copy(update={"service_account": None})}
    )
    collector = validate_deployment(ship_project.data, deployment, profile="prod-readonly")

    assert collector.has_errors()
    assert any(d.code == "AGK-CLOUD-002" for d in collector.errors())


def test_prod_readonly_requires_policies(hello_world_agent_dir: Path) -> None:
    """Production profiles require policies.yaml when security checks run."""
    project = AgentProject.load(hello_world_agent_dir)
    collector = validate_project(
        project.root,
        project.data,
        level="security",
        profile="prod-readonly",
    )

    assert collector.has_errors()
    assert any(d.code == "AGK-POLICY-003" for d in collector.errors())


def test_assert_valid_project_raises_on_errors(hello_world_agent_dir: Path) -> None:
    """assert_valid_project raises ValidationError when diagnostics include errors."""
    project = AgentProject.load(hello_world_agent_dir)

    with pytest.raises(ValidationError):
        assert_valid_project(
            project.root,
            project.data,
            level="security",
            profile="prod-readonly",
        )


def test_dev_restricted_warns_on_missing_dangerous_tool_denies(hello_world_agent_dir: Path) -> None:
    """dev-restricted does not require policies; prod profiles warn on missing denies."""
    project = AgentProject.load(hello_world_agent_dir)
    collector = validate_project(
        project.root,
        project.data,
        level="security",
        profile="dev-restricted",
    )

    assert not collector.has_errors()


@pytest.mark.parametrize(
    ("allowed_servers", "expected_error"),
    [
        (None, True),
        ([], True),
        (["unrelated"], True),
        (["clock"], False),
    ],
)
def test_restricted_profiles_enforce_mcp_admission_allowlist(
    mcp_agent_dir: Path,
    allowed_servers: list[str] | None,
    expected_error: bool,
) -> None:
    """Missing, empty, and partial admission policies reject configured MCP servers."""
    project = AgentProject.load(mcp_agent_dir)
    mcp_spec = project.manifest.spec.mcp
    assert mcp_spec is not None
    mcp_spec.admission_policy = (
        None
        if allowed_servers is None
        else McpAdmissionPolicy.model_validate({"allowedServers": allowed_servers})
    )

    collector = validate_project(
        project.root,
        project.data,
        level="security",
        profile="dev-restricted",
    )

    admission_errors = [item for item in collector.errors() if item.code == "AGK-MCP-005"]
    assert bool(admission_errors) is expected_error
