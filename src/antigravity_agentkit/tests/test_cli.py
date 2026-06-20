"""Tests for Typer CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from antigravity_agentkit.cli import _print_plain, app
from antigravity_agentkit.schema.agent import AgentManifest

runner = CliRunner()


def test_cli_init_creates_valid_manifest(tmp_path: Path) -> None:
    """init writes a schema-valid YAML manifest."""
    result = runner.invoke(app, ["init", "valid-agent", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    raw = yaml.safe_load((tmp_path / "valid-agent" / "agent.yaml").read_text(encoding="utf-8"))
    manifest = AgentManifest.model_validate(raw)
    assert manifest.metadata.name == "valid-agent"


def test_cli_init_rejects_invalid_name_without_creating_directory(tmp_path: Path) -> None:
    """init validates names before writing scaffold files."""
    invalid_name = "Bad: Name"
    result = runner.invoke(app, ["init", invalid_name, "--output-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "Invalid agent name" in result.stdout
    assert "Traceback" not in result.stdout
    assert not (tmp_path / invalid_name).exists()


def test_cli_validate_hello_agent(hello_world_agent_dir: Path) -> None:
    """antigravity-agentkit validate succeeds on hello-agent example."""
    result = runner.invoke(app, ["validate", str(hello_world_agent_dir)])

    assert result.exit_code == 0, result.stdout
    assert "Validation passed" in result.stdout


def test_cli_validate_mcp_agent(mcp_agent_dir: Path) -> None:
    """antigravity-agentkit validate succeeds on mcp example."""
    result = runner.invoke(
        app,
        ["validate", str(mcp_agent_dir), "--level", "full", "--profile", "dev-open"],
    )

    assert result.exit_code == 0, result.stdout
    assert "Validation passed" in result.stdout


def test_cli_validate_fails_for_missing_agent(tmp_path: Path) -> None:
    """antigravity-agentkit validate exits with error for missing agent directory."""
    result = runner.invoke(app, ["validate", str(tmp_path / "missing-agent")])

    assert result.exit_code == 1
    assert "Agent directory not found" in result.stdout
    assert "Traceback" not in result.stdout


def test_cli_validate_reports_malformed_manifest_without_traceback(tmp_path: Path) -> None:
    """Malformed agent YAML is reported as a concise CLI error."""
    agent_dir = tmp_path / "broken-agent"
    agent_dir.mkdir()
    (agent_dir / "agent.yaml").write_text("metadata:\n  name: bad: value\n", encoding="utf-8")

    result = runner.invoke(app, ["validate", str(agent_dir)])

    assert result.exit_code == 1
    assert "Invalid YAML" in result.stdout
    assert "Traceback" not in result.stdout


def test_cli_validate_reports_invalid_mcp_schema(tmp_path: Path) -> None:
    """Invalid MCP fields produce diagnostics instead of a Pydantic traceback."""
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
    (agent_dir / "mcp.json").write_text(
        json.dumps({"mcpServers": {"broken": {"command": ""}}}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", str(agent_dir), "--level", "schema"])

    assert result.exit_code == 1
    assert "AGK-MCP-002" in result.stdout
    assert "Traceback" not in result.stdout


def test_cli_validate_prod_profile_reports_errors(hello_world_agent_dir: Path) -> None:
    """antigravity-agentkit validate with prod profile reports policy/cloud errors."""
    result = runner.invoke(
        app,
        ["validate", str(hello_world_agent_dir), "--level", "cloud", "--profile", "prod-readonly"],
    )

    assert result.exit_code == 1
    assert "AGK-CLOUD-002" in result.stdout or "AGK-POLICY-003" in result.stdout


def test_cli_compile_hello_agent(hello_world_agent_dir: Path) -> None:
    """antigravity-agentkit compile emits compiled config summary."""
    result = runner.invoke(app, ["compile", str(hello_world_agent_dir)])

    assert result.exit_code == 0, result.stdout
    assert "systemInstructionsLength" in result.stdout
    assert '"mcpServerCount": 0' in result.stdout


def test_cli_compile_mcp_agent(mcp_agent_dir: Path, tmp_path: Path) -> None:
    """antigravity-agentkit compile writes JSON output for mcp example."""
    output_file = tmp_path / "compiled.json"
    result = runner.invoke(
        app,
        ["compile", str(mcp_agent_dir), "--output", str(output_file)],
    )

    assert result.exit_code == 0, result.stdout
    assert output_file.is_file()
    content = output_file.read_text(encoding="utf-8")
    assert '"mcpServerCount": 1' in content
    assert '"policyCount"' in content


def test_cli_eval_mcp_agent(mcp_agent_dir: Path) -> None:
    """antigravity-agentkit eval runs mock-mode evals on mcp example."""
    result = runner.invoke(app, ["eval", str(mcp_agent_dir)])

    assert result.exit_code == 0, result.stdout
    assert "PASS" in result.stdout
    assert "1/1 passed" in result.stdout


@pytest.mark.parametrize("command", ["run", "chat"])
def test_cli_local_session_help_includes_interactive_flag(command: str) -> None:
    """run and chat document the interactive approval flag."""
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0, result.stdout
    assert "-interactive" in result.stdout
    if command == "chat":
        assert "--prompt" in result.stdout


def test_cli_chat_invokes_run_repl(
    hello_world_agent_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """chat command wires through to RuntimeAgent.run_repl."""
    calls: list[dict[str, object]] = []

    async def fake_run_repl(runtime_agent: object, **kwargs: object) -> None:
        del runtime_agent
        calls.append(kwargs)

    monkeypatch.setattr(
        "antigravity_agentkit.runtime.RuntimeAgent.run_repl",
        fake_run_repl,
    )

    result = runner.invoke(
        app,
        ["chat", str(hello_world_agent_dir), "--prompt", "hi"],
    )

    assert result.exit_code == 0, result.stdout
    assert len(calls) == 1
    assert calls[0]["initial_prompt"] == "hi"
    assert "Chat with hello-world" in result.stdout


def test_print_plain_does_not_interpret_markup() -> None:
    """Agent output with bracketed paths must not crash Rich markup rendering."""
    _print_plain("[/Users/yu/local/src/github/antigravity-agentkit]")
