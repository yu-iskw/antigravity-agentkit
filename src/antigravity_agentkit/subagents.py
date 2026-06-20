"""Markdown subagent loader and delegation tool compiler."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.exceptions import LoadError, ValidationError
from antigravity_agentkit.schema.agent import SubagentSpec
from antigravity_agentkit.schema.subagents import DelegationToolMetadata, LoadedSubagent
from antigravity_agentkit.skills import parse_frontmatter


def load_subagent_md(path: Path) -> LoadedSubagent:
    """Load a markdown subagent definition with YAML frontmatter."""
    if not path.is_file():
        raise LoadError(f"Subagent file not found: {path}")
    content = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(content)
    name = frontmatter.get("name")
    if not name or not isinstance(name, str):
        raise ValidationError(f"Subagent missing required frontmatter 'name': {path}")
    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        description = str(description)
    tools_raw = frontmatter.get("tools", [])
    if not isinstance(tools_raw, list):
        raise ValidationError(f"Subagent 'tools' must be a list: {path}")
    tools = [str(item) for item in tools_raw]
    return LoadedSubagent(
        name=name,
        description=description.strip(),
        path=path,
        frontmatter=frontmatter,
        body=body.strip(),
        tools=tools,
    )


def load_subagents_from_specs(
    root: Path,
    specs: list[SubagentSpec],
) -> dict[str, LoadedSubagent]:
    """Load markdown subagents declared in agent.yaml."""
    subagents: dict[str, LoadedSubagent] = {}
    for spec in specs:
        if spec.type != "markdown":
            continue
        if not spec.file:
            raise ValidationError(f"Markdown subagent '{spec.name}' missing 'file'")
        path = (root / spec.file).resolve()
        subagent = load_subagent_md(path)
        if subagent.name != spec.name:
            raise ValidationError(
                f"Subagent name mismatch: manifest={spec.name!r}, file={subagent.name!r}"
            )
        if spec.tools:
            subagent.tools = list(spec.tools)
        subagents[subagent.name] = subagent
    return subagents


def discover_subagents(root: Path, subagents_dir: str = "subagents") -> dict[str, LoadedSubagent]:
    """Discover and load all markdown subagents under subagents/."""
    base = root / subagents_dir
    if not base.is_dir():
        return {}
    subagents: dict[str, LoadedSubagent] = {}
    for path in sorted(base.glob("*.md")):
        subagent = load_subagent_md(path)
        subagents[subagent.name] = subagent
    return subagents


def compile_delegation_metadata(subagent: LoadedSubagent) -> DelegationToolMetadata:
    """Compile subagent metadata for a delegation tool."""
    description = subagent.description or f"Delegate tasks to the {subagent.name} subagent."
    return DelegationToolMetadata(
        name=subagent.name,
        description=description,
        subagent_name=subagent.name,
        tools=list(subagent.tools),
        system_instructions=subagent.body,
    )


def compile_delegation_tools(
    subagents: dict[str, LoadedSubagent],
) -> list[DelegationToolMetadata]:
    """Compile delegation tool metadata for all loaded subagents."""
    return [
        compile_delegation_metadata(subagent)
        for subagent in sorted(subagents.values(), key=lambda item: item.name)
    ]


def delegation_tool_dict(metadata: DelegationToolMetadata) -> dict[str, Any]:
    """Return a serializable delegation tool definition."""
    return {
        "name": metadata.tool_name,
        "description": metadata.description,
        "subagent": metadata.subagent_name,
        "tools": list(metadata.tools),
        "system_instructions": metadata.system_instructions,
    }
