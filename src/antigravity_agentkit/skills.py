"""Local SKILL.md loader, validator, and index builder."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from antigravity_agentkit.exceptions import LoadError, ValidationError
from antigravity_agentkit.paths import resolve_project_path
from antigravity_agentkit.schema.skills import (
    LoadedSkill,
    SkillFrontmatter,
    SkillIndex,
    SkillIndexEntry,
)

SKILL_FILENAME = "SKILL.md"
SKILL_FRONTMATTER_PARTS = 3
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and markdown body from a file."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < SKILL_FRONTMATTER_PARTS:
        return {}, content
    frontmatter_raw = parts[1]
    body = parts[2].lstrip("\n")
    try:
        frontmatter = yaml.safe_load(frontmatter_raw) or {}
    except yaml.YAMLError as exc:
        raise LoadError(f"Invalid YAML frontmatter: {exc}") from exc
    if not isinstance(frontmatter, dict):
        raise LoadError("Skill frontmatter must be a YAML mapping")
    return frontmatter, body


def validate_skill_name(name: str) -> None:
    """Validate skill name follows lowercase-hyphen convention."""
    if not name:
        raise ValidationError("Skill name is required")
    if not NAME_PATTERN.match(name):
        raise ValidationError(f"Skill name must use lowercase-hyphen format: {name!r}")


def validate_skill_frontmatter(frontmatter: dict[str, Any]) -> SkillFrontmatter:
    """Validate and parse skill frontmatter."""
    try:
        return SkillFrontmatter.model_validate(frontmatter)
    except Exception as exc:
        raise ValidationError(f"Invalid skill frontmatter: {exc}") from exc


def load_skill_md(path: Path) -> LoadedSkill:
    """Load a single SKILL.md file."""
    if not path.is_file():
        raise LoadError(f"SKILL.md not found: {path}")
    content = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(content)
    parsed = validate_skill_frontmatter(frontmatter)
    return LoadedSkill(
        name=parsed.name,
        description=parsed.description,
        path=path,
        frontmatter=frontmatter,
        body=body,
        content=content,
    )


def load_skill_directory(skill_dir: Path) -> LoadedSkill:
    """Load a skill package directory containing SKILL.md."""
    skill_path = skill_dir / SKILL_FILENAME
    if not skill_path.is_file():
        raise LoadError(f"Skill package missing {SKILL_FILENAME}: {skill_dir}")
    return load_skill_md(skill_path)


def load_skills(root: Path, local_paths: list[str]) -> dict[str, LoadedSkill]:
    """Load local skill packages referenced in agent.yaml."""
    skills: dict[str, LoadedSkill] = {}
    for rel_path in local_paths:
        skill_dir = resolve_project_path(root, rel_path, label="Skill directory")
        if not skill_dir.is_dir():
            raise LoadError(f"Skill directory not found: {skill_dir}")
        skill_path = resolve_project_path(
            root,
            (Path(rel_path) / SKILL_FILENAME).as_posix(),
            label="Skill file",
        )
        skill = load_skill_md(skill_path)
        skills[skill.name] = skill
    return skills


def discover_skills(root: Path, skills_dir: str = "skills") -> dict[str, LoadedSkill]:
    """Discover and load all skills under a skills/ directory."""
    project_root = root.resolve()
    base = resolve_project_path(project_root, skills_dir, label="Skills directory")
    if not base.is_dir():
        return {}
    skills: dict[str, LoadedSkill] = {}
    for skill_path in sorted(base.rglob(SKILL_FILENAME)):
        relative_path = skill_path.relative_to(project_root).as_posix()
        resolved_path = resolve_project_path(project_root, relative_path, label="Skill file")
        skill = load_skill_md(resolved_path)
        skills[skill.name] = skill
    return skills


def build_skill_index(skills: dict[str, LoadedSkill]) -> SkillIndex:
    """Build a compact skill index from loaded skills."""
    entries = [
        SkillIndexEntry(name=skill.name, description=skill.description, path=skill.path)
        for skill in sorted(skills.values(), key=lambda item: item.name)
    ]
    return SkillIndex(entries=entries)


def compile_skills_paths(skills: dict[str, LoadedSkill]) -> list[str]:
    """Return absolute skill package directories for SDK skills_paths."""
    return sorted({str(skill.path.parent) for skill in skills.values()})


def read_skill(skills: dict[str, LoadedSkill], name: str) -> str:
    """Return full SKILL.md content for the named skill."""
    skill = skills.get(name)
    if skill is None:
        available = ", ".join(sorted(skills)) or "(none)"
        raise LoadError(f"Skill not found: {name!r}. Available: {available}")
    return skill.content


def validate_skills(root: Path, local_paths: list[str]) -> dict[str, LoadedSkill]:
    """Load and validate all referenced local skills."""
    return load_skills(root, local_paths)
