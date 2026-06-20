"""Schema models for subagent markdown definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LoadedSubagent:
    """Loaded markdown subagent definition."""

    name: str
    description: str
    path: Path
    frontmatter: dict[str, Any]
    body: str
    tools: list[str]


@dataclass
class DelegationToolMetadata:
    """Metadata for a compiled subagent delegation tool."""

    name: str
    description: str
    subagent_name: str
    tools: list[str]
    system_instructions: str

    @property
    def tool_name(self) -> str:
        """Return the delegation tool function name."""
        safe_name = self.subagent_name.replace("-", "_")
        return f"delegate_to_{safe_name}"
