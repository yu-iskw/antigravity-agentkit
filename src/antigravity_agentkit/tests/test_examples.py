"""Tests for all bundled example agents."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from antigravity_agentkit.cli import app
from antigravity_agentkit.compiler import compile_agent_config
from antigravity_agentkit.loader import load_agent_directory
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.validator import validate_project

runner = CliRunner()

try:
    _HAS_ANTIGRAVITY_SDK = importlib.util.find_spec("google.antigravity") is not None
except ModuleNotFoundError:
    _HAS_ANTIGRAVITY_SDK = False

EXAMPLE_NAMES = ("hello_world", "mcp", "skills", "subagents")


@pytest.mark.parametrize("example_name", EXAMPLE_NAMES)
def test_example_manifest_uses_gemini_flash_preview(example_name: str, repo_root: Path) -> None:
    """Each example pins gemini-3.1-flash-lite for cost-efficient demos."""
    data = load_agent_directory(repo_root / "examples" / example_name)

    assert data.manifest.spec.runtime.model == "gemini-3.1-flash-lite"


@pytest.mark.parametrize("example_name", EXAMPLE_NAMES)
def test_example_validate_via_api(example_name: str, repo_root: Path) -> None:
    """Every bundled example passes schema validation."""
    path = repo_root / "examples" / example_name
    project = AgentProject.load(path)
    level = "full" if example_name == "mcp" else "schema"
    profile = "dev-open"
    collector = validate_project(project.root, project.data, level=level, profile=profile)

    assert not collector.has_errors(), collector.format_all()


@pytest.mark.parametrize("example_name", EXAMPLE_NAMES)
def test_example_compile_metadata(example_name: str, repo_root: Path) -> None:
    """Every example compiles to runtime metadata."""
    compiled = compile_agent_config(repo_root / "examples" / example_name)

    assert compiled.model == "gemini-3.1-flash-lite"
    assert compiled.system_instructions


def test_mcp_example_has_clock_server_and_policies(mcp_agent_dir: Path) -> None:
    """MCP example wires clock server, policies, skills, subagents, and evals."""
    data = load_agent_directory(mcp_agent_dir)

    assert data.mcp_config is not None
    assert "clock" in data.mcp_config.get("mcpServers", {})
    assert data.policies is not None
    assert "mcp-guide" in data.skills
    assert "time-checker" in data.subagents
    assert len(data.evals) == 1


@pytest.mark.live
@pytest.mark.skipif(
    not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
    reason="Set GEMINI_API_KEY or GOOGLE_API_KEY for live example run",
)
@pytest.mark.skipif(not _HAS_ANTIGRAVITY_SDK, reason="google-antigravity not installed")
def test_hello_world_live_run_cli(hello_world_agent_dir: Path) -> None:
    """hello_world runs one chat turn when SDK and API key are available."""
    result = runner.invoke(
        app,
        ["run", str(hello_world_agent_dir), "--prompt", "Reply with the word: ok"],
    )

    assert result.exit_code == 0, result.stdout
    assert "ChatResponse object at" not in result.stdout
    assert result.stdout.strip()
