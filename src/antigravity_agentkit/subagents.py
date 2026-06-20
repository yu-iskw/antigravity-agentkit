"""Markdown subagent loader and delegation tool compiler."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.exceptions import LoadError, ValidationError
from antigravity_agentkit.ir import SubagentIR
from antigravity_agentkit.paths import resolve_project_path
from antigravity_agentkit.schema.agent import SubagentSpec
from antigravity_agentkit.schema.subagents import DelegationToolMetadata, LoadedSubagent
from antigravity_agentkit.skills import parse_frontmatter, skill_content_hash


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
        path = resolve_project_path(root, spec.file, label="Subagent file")
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
    project_root = root.resolve()
    base = resolve_project_path(project_root, subagents_dir, label="Subagents directory")
    if not base.is_dir():
        return {}
    subagents: dict[str, LoadedSubagent] = {}
    for path in sorted(base.glob("*.md")):
        relative_path = path.relative_to(project_root).as_posix()
        resolved_path = resolve_project_path(project_root, relative_path, label="Subagent file")
        subagent = load_subagent_md(resolved_path)
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


def delegation_tool_dict_from_ir(entry: dict[str, Any]) -> dict[str, Any]:
    """Return serializable delegation metadata derived from subagent IR."""
    name = entry["name"]
    safe_name = name.replace("-", "_")
    return {
        "name": f"delegate_to_{safe_name}",
        "description": entry.get("description") or f"Delegate tasks to the {name} subagent.",
        "subagent": name,
        "tools": list(entry.get("tools") or []),
        "system_instructions": entry.get("systemInstructions", ""),
    }


def sdk_subagents_supported() -> bool:
    """Return True when the installed SDK can accept static subagents on LocalAgentConfig."""
    try:
        import inspect

        from google.antigravity import LocalAgentConfig, types
    except ImportError:
        return False
    if getattr(types, "SubagentConfig", None) is None:
        return False
    signature = inspect.signature(LocalAgentConfig)
    params = signature.parameters
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in params.values()
    )
    return "subagents" in params or accepts_kwargs


def delegation_tool_dict(metadata: DelegationToolMetadata) -> dict[str, Any]:
    """Return a serializable delegation tool definition."""
    return delegation_tool_dict_from_ir(
        {
            "name": metadata.subagent_name,
            "description": metadata.description,
            "systemInstructions": metadata.system_instructions,
            "tools": list(metadata.tools),
        }
    )


def _coerce_loaded_subagents(subagents: dict[str, object]) -> dict[str, LoadedSubagent]:
    """Coerce loaded subagents dict to LoadedSubagent instances."""
    result: dict[str, LoadedSubagent] = {}
    for name, subagent in subagents.items():
        if isinstance(subagent, LoadedSubagent):
            result[name] = subagent
    return result


def compile_subagents_to_ir(
    root: Path,
    subagents: dict[str, LoadedSubagent],
) -> tuple[SubagentIR, ...]:
    """Compile loaded subagents into frozen subagent IR."""
    project_root = root.resolve()
    entries: list[SubagentIR] = []
    for subagent in sorted(subagents.values(), key=lambda item: item.name):
        relative_path = subagent.path.relative_to(project_root).as_posix()
        content_hash = skill_content_hash(subagent.body)
        entries.append(
            SubagentIR(
                name=subagent.name,
                type="markdown",
                path=relative_path,
                content_hash=content_hash,
                description=subagent.description,
                system_instructions=subagent.body,
                tools=tuple(subagent.tools),
            )
        )
    return tuple(entries)


def compile_subagent_ir(subagents: dict[str, Any]) -> list[dict[str, Any]]:
    """Compile loaded subagents into serializable IR for the SDK emitter."""
    loaded = _coerce_loaded_subagents(subagents)
    return [
        {
            "name": subagent.name,
            "description": subagent.description,
            "systemInstructions": subagent.body,
            "tools": list(subagent.tools),
        }
        for subagent in sorted(loaded.values(), key=lambda item: item.name)
    ]


def subagent_index_section(
    subagent_ir: list[dict[str, Any]],
    *,
    enable_subagents: bool = True,
) -> str:
    """Render subagent definitions for system-instruction injection."""
    if not subagent_ir or not enable_subagents or sdk_subagents_supported():
        return ""

    lines = ["## Available Subagents", ""]
    for entry in subagent_ir:
        name = entry["name"]
        lines.append(f"### {name}")
        if entry.get("description"):
            lines.append(entry["description"])
        if entry.get("tools"):
            tool_list = ", ".join(f"`{tool}`" for tool in entry["tools"])
            lines.append(f"Allowed tools: {tool_list}")
        lines.append("")
        lines.append(entry.get("systemInstructions", "").strip())
        lines.append("")
    return "\n".join(lines).strip()
