"""Tests for SKILL.md loading and frontmatter validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_agentkit.exceptions import LoadError, ValidationError
from antigravity_agentkit.skills import (
    compile_skills_paths,
    discover_skills,
    load_skill_md,
    parse_frontmatter,
    validate_skill_frontmatter,
    validate_skill_name,
)


def test_load_greeting_helper_skill(skills_agent_dir: Path) -> None:
    """Load greeting-helper skill from skills example."""
    skill_path = skills_agent_dir / "skills" / "greeting-helper" / "SKILL.md"
    skill = load_skill_md(skill_path)

    assert skill.name == "greeting-helper"
    assert "greeting" in skill.description.lower()
    assert skill.frontmatter["license"] == "Apache-2.0"
    assert "# Greeting Helper Skill" in skill.body


def test_discover_skills_in_example(skills_agent_dir: Path) -> None:
    """discover_skills finds all skills under skills/."""
    skills = discover_skills(skills_agent_dir)

    assert set(skills) == {"greeting-helper"}


def test_compile_skills_paths_returns_absolute_package_dirs(skills_agent_dir: Path) -> None:
    """compile_skills_paths returns deduplicated absolute skill package directories."""
    skills = discover_skills(skills_agent_dir)
    paths = compile_skills_paths(skills)

    assert len(paths) == 1
    assert paths[0] == str((skills_agent_dir / "skills" / "greeting-helper").resolve())


def test_parse_frontmatter_extracts_body() -> None:
    """parse_frontmatter splits YAML frontmatter from markdown body."""
    content = "---\nname: demo-skill\ndescription: A demo skill for testing.\n---\n# Demo\n"
    frontmatter, body = parse_frontmatter(content)

    assert frontmatter["name"] == "demo-skill"
    assert body.startswith("# Demo")


def test_parse_frontmatter_without_delimiters() -> None:
    """Files without frontmatter return empty dict and full content."""
    content = "# No frontmatter here\n"
    frontmatter, body = parse_frontmatter(content)

    assert frontmatter == {}
    assert body == content


def test_validate_skill_frontmatter_requires_name_and_description() -> None:
    """Skill frontmatter must include name and description."""
    with pytest.raises(ValidationError, match="name"):
        validate_skill_frontmatter({"description": "missing name"})

    with pytest.raises(ValidationError, match="description"):
        validate_skill_frontmatter({"name": "demo-skill"})


@pytest.mark.parametrize(
    "bad_name",
    [
        "BigQuery-Analysis",
        "bigquery_analysis",
        "-skill",
    ],
)
def test_validate_skill_name_rejects_invalid_names(bad_name: str) -> None:
    """Skill names must be lowercase hyphenated."""
    with pytest.raises(ValidationError):
        validate_skill_name(bad_name)


def test_validate_skill_frontmatter_rejects_digit_leading_name() -> None:
    """Skill frontmatter names must start with a lowercase letter."""
    with pytest.raises(ValidationError):
        validate_skill_frontmatter(
            {
                "name": "1skill",
                "description": "Invalid leading digit in skill name.",
            }
        )


def test_validate_skill_frontmatter_rejects_unknown_fields() -> None:
    """extra='forbid' rejects unknown frontmatter keys."""
    with pytest.raises(ValidationError):
        validate_skill_frontmatter(
            {
                "name": "demo-skill",
                "description": "Valid description for testing.",
                "author": "someone",
            }
        )


def test_load_skill_md_missing_file_raises(tmp_path: Path) -> None:
    """Missing SKILL.md raises LoadError."""
    with pytest.raises(LoadError, match="SKILL.md not found"):
        load_skill_md(tmp_path / "SKILL.md")
