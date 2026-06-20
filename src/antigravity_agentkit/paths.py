"""Safe path helpers for agent project assets."""

from __future__ import annotations

from pathlib import Path

from antigravity_agentkit.exceptions import LoadError


def resolve_project_path(root: Path, relative_path: str, *, label: str) -> Path:
    """Resolve a relative asset path and require it to remain inside the project."""
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise LoadError(f"{label} path must be relative: {relative_path}")

    project_root = root.resolve()
    resolved = (project_root / candidate).resolve()
    if not resolved.is_relative_to(project_root):
        raise LoadError(f"{label} path escapes the agent directory: {relative_path}")
    return resolved
