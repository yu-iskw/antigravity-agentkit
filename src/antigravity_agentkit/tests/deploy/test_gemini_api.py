"""Tests for Gemini API deployment adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from antigravity_agentkit.deploy import build_deployment_config, deploy
from antigravity_agentkit.deploy.gemini_api import _unsupported_features
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.agent import CompiledAgentConfig
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.tests.constants import TEST_GCP_LOCATION, TEST_GCP_PROJECT
from antigravity_agentkit.tests.deploy.conftest import write_minimal_agent

_BASE_AGENT = "antigravity-preview-05-2026"


def _deployment(name: str = "test-agent") -> DeploymentManifest:
    return DeploymentManifest.model_validate(
        {
            "apiVersion": "antigravity-agentkit.dev/v1alpha1",
            "kind": "Deployment",
            "metadata": {"name": name},
            "spec": {"target": "gemini-api"},
        }
    )


def test_build_gemini_api_config_maps_agents_create_fields(tmp_path: Path) -> None:
    """Gemini API contract is a submit-ready agents.create request body."""
    agent_dir = tmp_path / "agent"
    write_minimal_agent(agent_dir)
    skill_dir = agent_dir / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill_content = "---\nname: demo\ndescription: Demo skill\n---\n\n# Demo\n"
    (skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")
    agent_yaml = agent_dir / "agent.yaml"
    agent_yaml.write_text(
        agent_yaml.read_text(encoding="utf-8").replace(
            "  name: test-agent", "  name: test-agent\n  description: Test description"
        )
        + "\n  runtime:\n    model: gemini-3.1-flash-lite\n"
        + "  skills:\n    local:\n      - skills/demo\n",
        encoding="utf-8",
    )
    project = AgentProject.load(agent_dir)

    config = build_deployment_config(
        project,
        _deployment("managed-agent-id"),
        TEST_GCP_PROJECT,
        TEST_GCP_LOCATION,
    )

    assert config == {
        "id": "managed-agent-id",
        "base_agent": _BASE_AGENT,
        "description": "Test description",
        "system_instruction": "# Agent\n",
        "base_environment": {
            "type": "remote",
            "sources": [
                {
                    "type": "inline",
                    "target": ".agents/skills/demo/SKILL.md",
                    "content": skill_content,
                }
            ],
        },
    }
    assert "read_skill" not in config["system_instruction"]


def test_build_gemini_api_config_without_skills_uses_remote_environment(
    gemini_deploy_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """Agents without skills use the short remote environment form."""
    project, deployment = gemini_deploy_context

    config = build_deployment_config(
        project,
        deployment,
        TEST_GCP_PROJECT,
        TEST_GCP_LOCATION,
    )

    assert config["base_environment"] == "remote"
    assert "description" not in config


@pytest.mark.parametrize(
    ("feature", "expected"),
    [
        ("mcp", ["mcp"]),
        ("subagents", ["subagents"]),
        ("policies", ["policies"]),
        ("capabilities", ["capabilities"]),
        ("vertex", ["vertex"]),
    ],
)
def test_unsupported_features_cover_unrepresentable_configuration(
    feature: str,
    expected: list[str],
) -> None:
    """Every unrepresentable feature is identified before emission."""
    compiled = CompiledAgentConfig(system_instructions="# Agent")
    if feature == "mcp":
        compiled.mcp_servers = [{"name": "demo"}]
    elif feature == "subagents":
        compiled.subagents = [{"name": "helper"}]
    elif feature == "policies":
        compiled.policies = [{"name": "deny"}]
    elif feature == "vertex":
        compiled.vertex = {"enabled": True}

    assert (
        _unsupported_features(
            compiled,
            has_non_default_capabilities=feature == "capabilities",
        )
        == expected
    )


def test_deploy_rejects_unsupported_features_without_writing_artifact(
    subagents_agent_dir: Path,
    tmp_path: Path,
) -> None:
    """Unsupported projects fail without leaving a degraded contract."""
    project = AgentProject.load(subagents_agent_dir)
    out = tmp_path / "gemini-agent-config.json"

    with pytest.raises(DeployError, match="subagents"):
        deploy(
            project,
            _deployment("subagent-demo"),
            TEST_GCP_PROJECT,
            TEST_GCP_LOCATION,
            output_path=out,
            dry_run=True,
        )

    assert not out.exists()


def test_deploy_gemini_api_dry_run_writes_config(
    gemini_deploy_context: tuple[AgentProject, DeploymentManifest],
    tmp_path: Path,
) -> None:
    """Dry-run deploy writes gemini-agent-config.json without packaging."""
    project, deployment = gemini_deploy_context
    out = tmp_path / "gemini-agent-config.json"

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
    assert summary["config"]["id"] == "test-agent"
    assert "package_dir" not in summary

    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["base_agent"] == _BASE_AGENT


def test_deploy_gemini_api_implicit_dry_run_with_credentials(
    gemini_deploy_context: tuple[AgentProject, DeploymentManifest],
    tmp_path: Path,
) -> None:
    """Gemini API deploy dry-runs even when GCP credentials are present."""
    project, deployment = gemini_deploy_context
    out = tmp_path / "gemini-agent-config.json"

    summary = deploy(
        project,
        deployment,
        TEST_GCP_PROJECT,
        TEST_GCP_LOCATION,
        output_path=out,
        dry_run=None,
    )

    assert summary["status"] == "dry_run"
    assert Path(summary["config_path"]).is_file()


def test_deploy_gemini_api_live_raises_not_implemented(
    gemini_deploy_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """Live Gemini API deploy raises until Agents API apply is implemented."""
    project, deployment = gemini_deploy_context

    with pytest.raises(DeployError, match="not implemented"):
        deploy(
            project,
            deployment,
            TEST_GCP_PROJECT,
            TEST_GCP_LOCATION,
            dry_run=False,
        )
