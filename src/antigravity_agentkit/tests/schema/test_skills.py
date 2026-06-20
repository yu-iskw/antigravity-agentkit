"""Tests for skill schema models."""

from __future__ import annotations

from pathlib import Path

from antigravity_agentkit.schema.skills import SkillIndex, SkillIndexEntry


def test_skill_index_to_prompt_section_renders_entries() -> None:
    """SkillIndex renders a compact prompt section for available skills."""
    index = SkillIndex(
        entries=[
            SkillIndexEntry(
                name="greeting-helper",
                description="Greets the user.",
                path=Path("skills/greeting-helper/SKILL.md"),
            )
        ]
    )

    section = index.to_prompt_section()

    assert "## Available Skills" in section
    assert "**greeting-helper**: Greets the user." in section
    assert "read_skill" in section


def test_skill_index_empty_returns_empty_string() -> None:
    """An empty skill index renders no prompt section."""
    assert SkillIndex().to_prompt_section() == ""
