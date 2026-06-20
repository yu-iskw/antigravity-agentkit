"""Tests for Typer CLI commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from antigravity_agentkit.cli import _print_plain, app

runner = CliRunner()


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


def test_cli_run_help_includes_interactive_flag() -> None:
    """run command documents the interactive approval flag."""
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0, result.stdout
    assert "-interactive" in result.stdout


def test_print_plain_does_not_interpret_markup() -> None:
    """Agent output with bracketed paths must not crash Rich markup rendering."""
    _print_plain("[/Users/yu/local/src/github/antigravity-agentkit]")
