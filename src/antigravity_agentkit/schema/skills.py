"""Schema models for SKILL.md packages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SKILL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
_MAX_DESCRIPTION_LENGTH = 1024


class SkillFrontmatter(BaseModel):
    """YAML frontmatter from a SKILL.md package."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=_MAX_DESCRIPTION_LENGTH)
    license: str | None = Field(default=None, min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name_convention(cls, value: str) -> str:
        """Enforce lowercase hyphenated skill names per Skill Registry rules."""
        stripped = value.strip()
        if not _SKILL_NAME_PATTERN.match(stripped):
            msg = (
                "Skill name must start with a lowercase letter and contain only "
                "lowercase letters, digits, and hyphens."
            )
            raise ValueError(msg)
        return stripped

    @field_validator("description")
    @classmethod
    def validate_description_not_blank(cls, value: str) -> str:
        """Reject blank skill descriptions."""
        stripped = value.strip()
        if not stripped:
            msg = "Skill description must not be blank."
            raise ValueError(msg)
        return stripped


@dataclass
class SkillIndexEntry:
    """Compact skill index entry for progressive disclosure."""

    name: str
    description: str
    path: Path


@dataclass
class SkillIndex:
    """Index of available skills."""

    entries: list[SkillIndexEntry] = field(default_factory=list)

    def to_prompt_section(self) -> str:
        """Render a compact skill index for system context."""
        if not self.entries:
            return ""
        lines = ["## Available Skills", ""]
        for entry in self.entries:
            lines.append(f"- **{entry.name}**: {entry.description}")
        lines.append("")
        lines.append("Use the `read_skill` tool to load full skill instructions when needed.")
        return "\n".join(lines)


@dataclass
class LoadedSkill:
    """Fully loaded local skill package."""

    name: str
    description: str
    path: Path
    frontmatter: dict[str, Any]
    body: str
    content: str
