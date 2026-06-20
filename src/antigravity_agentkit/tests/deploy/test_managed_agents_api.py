"""Tests for Managed Agents API deployment adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from antigravity_agentkit.deploy import build_deployment_config, deploy
from antigravity_agentkit.deploy.capabilities import (
    MANAGED_AGENTS_API_CAPABILITIES,
    unsupported_features_for_target,
)
from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.ir import (
    IR_SCHEMA_VERSION,
    CapabilitiesIR,
    CompiledAgentIR,
    McpServerIR,
    PolicyRuleIR,
    SubagentIR,
    VertexIR,
)
from antigravity_agentkit.project import AgentProject
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


def test_build_managed_agents_config_maps_agents_create_fields(tmp_path: Path) -> None:
    """Managed Agents API contract is a submit-ready agents.create request body."""
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

    assert config["id"] == "managed-agent-id"
    assert config["base_agent"] == _BASE_AGENT
    assert config["description"] == "Test description"
    assert config["system_instruction"].startswith("# Agent\n")
    assert "demo" in config["system_instruction"]
    assert config["base_environment"]["type"] == "remote"
    assert config["registry"] == {"scope": "global"}


def test_build_managed_agents_config_without_skills_uses_remote_environment(
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
    ("mutator", "expected"),
    [
        (
            lambda ir: CompiledAgentIR(
                schema_version=ir.schema_version,
                system_instructions=ir.system_instructions,
                mcp_servers=(McpServerIR(name="demo", transport="stdio", command="x"),),
            ),
            ("mcp",),
        ),
        (
            lambda ir: CompiledAgentIR(
                schema_version=ir.schema_version,
                system_instructions=ir.system_instructions,
                subagents=(SubagentIR(name="helper", type="markdown"),),
            ),
            ("subagents",),
        ),
        (
            lambda ir: CompiledAgentIR(
                schema_version=ir.schema_version,
                system_instructions=ir.system_instructions,
                policies=(PolicyRuleIR(decision="deny", tool="run_command"),),
            ),
            ("policies",),
        ),
        (
            lambda ir: CompiledAgentIR(
                schema_version=ir.schema_version,
                system_instructions=ir.system_instructions,
                capabilities=CapabilitiesIR(mode="open"),
            ),
            ("capabilities",),
        ),
        (
            lambda ir: CompiledAgentIR(
                schema_version=ir.schema_version,
                system_instructions=ir.system_instructions,
                vertex=VertexIR(enabled=True),
            ),
            ("vertex",),
        ),
    ],
)
def test_unsupported_features_cover_unrepresentable_configuration(
    mutator: object,
    expected: tuple[str, ...],
) -> None:
    """Every unrepresentable feature is identified before emission."""
    base = CompiledAgentIR(schema_version=IR_SCHEMA_VERSION, system_instructions="# Agent")
    ir = mutator(base)  # type: ignore[operator]
    assert unsupported_features_for_target(ir, MANAGED_AGENTS_API_CAPABILITIES) == expected


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


def test_deploy_managed_agents_dry_run_writes_config(
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


def test_deploy_managed_agents_implicit_dry_run_with_credentials(
    gemini_deploy_context: tuple[AgentProject, DeploymentManifest],
    tmp_path: Path,
) -> None:
    """Managed Agents API deploy dry-runs even when GCP credentials are present."""
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


def test_deploy_managed_agents_live_calls_api(
    gemini_deploy_context: tuple[AgentProject, DeploymentManifest],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live Managed Agents API deploy posts gemini-agent-config."""
    project, deployment = gemini_deploy_context
    calls: list[dict[str, object]] = []

    def fake_create(config: dict[str, object]) -> dict[str, object]:
        calls.append(config)
        return {"status": "deployed", "agentId": str(config.get("id", ""))}

    monkeypatch.setattr(
        "antigravity_agentkit.platform.managed_agents.create_managed_agent",
        fake_create,
    )

    summary = deploy(
        project,
        deployment,
        TEST_GCP_PROJECT,
        TEST_GCP_LOCATION,
        dry_run=False,
    )

    assert summary["status"] == "deployed"
    assert calls
