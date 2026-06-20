"""Shared pytest fixtures for antigravity-agentkit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HELLO_WORLD_DIR = REPO_ROOT / "examples" / "hello_world"
SHIP_AGENT_DIR = Path(__file__).resolve().parent / "fixtures" / "ship_agent"
MCP_DIR = REPO_ROOT / "examples" / "mcp"
SKILLS_DIR = REPO_ROOT / "examples" / "skills"
SUBAGENTS_DIR = REPO_ROOT / "examples" / "subagents"


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root directory."""
    return REPO_ROOT


@pytest.fixture
def ship_agent_dir() -> Path:
    """Return the ship-agent test fixture (agent + deployment.yaml)."""
    return SHIP_AGENT_DIR


@pytest.fixture
def hello_world_agent_dir() -> Path:
    """Return the hello_world example directory."""
    return HELLO_WORLD_DIR


@pytest.fixture
def mcp_agent_dir() -> Path:
    """Return the mcp example directory."""
    return MCP_DIR


@pytest.fixture
def skills_agent_dir() -> Path:
    """Return the skills example directory."""
    return SKILLS_DIR


@pytest.fixture
def subagents_agent_dir() -> Path:
    """Return the subagents example directory."""
    return SUBAGENTS_DIR
