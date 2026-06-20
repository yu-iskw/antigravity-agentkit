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
    """Return True when the installed SDK exposes static SubagentConfig."""
    try:
        from google.antigravity import types
    except ImportError:
        return False
    return getattr(types, "SubagentConfig", None) is not None


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


def _coerce_loaded_subagents(subagents: dict[str, Any]) -> dict[str, LoadedSubagent]:
    """Coerce loaded subagents dict to LoadedSubagent instances."""
    result: dict[str, LoadedSubagent] = {}
    for name, subagent in subagents.items():
        if isinstance(subagent, LoadedSubagent):
            result[name] = subagent
    return result


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


def try_compile_sdk_subagents(subagent_ir: list[dict[str, Any]]) -> list[Any]:
    """Compile subagent IR to SDK SubagentConfig objects when SDK is available."""
    if not subagent_ir:
        return []

    try:
        from google.antigravity import types
    except ImportError:
        return []

    subagent_config = getattr(types, "SubagentConfig", None)
    if subagent_config is None:
        return []

    sdk_subagents: list[Any] = []
    for entry in subagent_ir:
        kwargs: dict[str, Any] = {
            "name": entry["name"],
            "description": entry["description"],
            "system_instructions": entry["systemInstructions"],
        }
        tools = entry.get("tools") or []
        if tools:
            kwargs["tools"] = list(tools)
        sdk_subagents.append(subagent_config(**kwargs))
    return sdk_subagents


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
