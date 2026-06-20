"""Callable runtime tools compiled from loaded agent project data."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from antigravity_agentkit.exceptions import LoadError
from antigravity_agentkit.schema.skills import LoadedSkill


def build_read_skill_tool(skills: dict[str, LoadedSkill]) -> Callable[[str], str]:
    """Return a callable that loads full SKILL.md content by name."""

    def read_skill(name: str) -> str:
        skill = skills.get(name)
        if skill is None:
            available = ", ".join(sorted(skills)) or "(none)"
            raise LoadError(f"Skill not found: {name!r}. Available: {available}")
        return skill.content

    read_skill.__name__ = "read_skill"
    available = ", ".join(sorted(skills)) if skills else "(none)"
    read_skill.__doc__ = f"Load full instructions for a named skill. Available skills: {available}"
    return read_skill


def read_skill_tool_metadata(skills: dict[str, LoadedSkill]) -> dict[str, Any]:
    """Return serializable metadata describing the read_skill helper."""
    skill_names = sorted(skills.keys())
    available = ", ".join(skill_names) if skill_names else "(none)"
    return {
        "name": "read_skill",
        "description": f"Load full instructions for a named skill. Available skills: {available}",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Skill name to load",
                }
            },
            "required": ["name"],
        },
    }
