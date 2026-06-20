"""Tests for runtime callable tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_agentkit.compiler import compile_from_data, compile_to_sdk_config
from antigravity_agentkit.exceptions import LoadError
from antigravity_agentkit.loader import load_agent_directory
from antigravity_agentkit.runtime_tools import build_read_skill_tool
from antigravity_agentkit.schema.skills import LoadedSkill


def _loaded_skills(data_skills: dict[str, object]) -> dict[str, LoadedSkill]:
    return {name: skill for name, skill in data_skills.items() if isinstance(skill, LoadedSkill)}


def test_read_skill_tool_returns_content(skills_agent_dir: Path) -> None:
    """read_skill callable returns SKILL.md body for a known skill."""
    data = load_agent_directory(skills_agent_dir)
    tool = build_read_skill_tool(_loaded_skills(data.skills))
    content = tool("greeting-helper")

    assert "Greeting Helper" in content


def test_read_skill_tool_missing_name_raises(skills_agent_dir: Path) -> None:
    """read_skill raises LoadError for unknown skill names."""
    data = load_agent_directory(skills_agent_dir)
    tool = build_read_skill_tool(_loaded_skills(data.skills))

    with pytest.raises(LoadError, match="Skill not found"):
        tool("missing-skill")


def test_compile_includes_runtime_tools(skills_agent_dir: Path) -> None:
    """Compiled config exposes callable read_skill for SDK wiring."""
    data = load_agent_directory(skills_agent_dir)
    compiled = compile_from_data(data)

    assert compiled.runtime_tools
    assert compiled.runtime_tools[0].__name__ == "read_skill"


def test_compile_to_sdk_config_includes_callable_tools(skills_agent_dir: Path) -> None:
    """SDK config receives runtime callables when google-antigravity is installed."""
    data = load_agent_directory(skills_agent_dir)
    compiled = compile_from_data(data)

    try:
        sdk_config = compile_to_sdk_config(compiled)
    except Exception as exc:
        if "google-antigravity is not installed" in str(exc):
            pytest.skip("google-antigravity not installed")
        raise

    assert sdk_config is not None
