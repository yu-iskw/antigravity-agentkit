"""Build deployable source packages from compiled agent configuration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from antigravity_agentkit.exceptions import DeployError, LoadError
from antigravity_agentkit.paths import resolve_project_path
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.agent import CompiledAgentConfig

_EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".build",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
    }
)
_EXCLUDED_FILE_NAMES = frozenset({".DS_Store"})


def _is_excluded(relative_path: Path) -> bool:
    """Return whether a source path is a development or secret artifact."""
    if any(part in _EXCLUDED_DIRECTORY_NAMES for part in relative_path.parts):
        return True
    name = relative_path.name
    return (
        name in _EXCLUDED_FILE_NAMES
        or name == ".env"
        or name.startswith(".env.")
        or relative_path.suffix == ".pyc"
    )


def _package_entries(project_root: Path) -> list[tuple[Path, Path]]:
    """Return validated source entries and their relative package paths."""
    entries: list[tuple[Path, Path]] = []
    for source_entry in sorted(project_root.rglob("*")):
        relative_path = source_entry.relative_to(project_root)
        if _is_excluded(relative_path):
            continue
        if source_entry.is_symlink():
            raise DeployError(f"Symlinks are not allowed in source packages: {source_entry}")

        try:
            source = resolve_project_path(
                project_root,
                relative_path.as_posix(),
                label="Package source",
            )
        except LoadError as exc:
            raise DeployError(str(exc)) from exc
        entries.append((source, relative_path))
    return entries


def _copy_project_tree(entries: list[tuple[Path, Path]], build_root: Path) -> None:
    """Copy validated agent source entries into the package."""
    for source, relative_path in entries:
        destination = build_root / relative_path
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _validate_build_root(project_root: Path, build_root: Path) -> None:
    """Reject output locations that could delete agent source files."""
    if build_root == project_root or project_root.is_relative_to(build_root):
        raise DeployError(f"Package output cannot contain the agent directory: {build_root}")

    if build_root.is_relative_to(project_root):
        project_build_root = (project_root / ".build").resolve()
        if not build_root.is_relative_to(project_build_root):
            raise DeployError(
                "Package output inside the agent directory must be under "
                f"{project_build_root}: {build_root}"
            )


def _write_package_files(
    project: AgentProject,
    build_root: Path,
    compiled: CompiledAgentConfig,
) -> None:
    """Write generated runtime entrypoint and package metadata."""
    manifest = project.data.manifest

    metadata = {
        "agentName": manifest.metadata.name,
        "compiled": {
            "vertex": compiled.vertex,
            "mcpServers": [server.get("name") for server in compiled.mcp_servers],
            "toolCount": len(compiled.tools),
            "policyCount": len(compiled.policies),
        },
    }
    (build_root / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    entrypoint = (
        '"""Generated Antigravity AgentKit runtime entrypoint."""\n\n'
        "from antigravity_agentkit.project import AgentProject\n\n"
        'root_agent = AgentProject.load(".").create_agent()\n'
    )
    (build_root / "agent.py").write_text(entrypoint, encoding="utf-8")

    requirements = "antigravity-agentkit[antigravity]\n"
    (build_root / "requirements.txt").write_text(requirements, encoding="utf-8")


def build_source_package(
    project: AgentProject,
    output_dir: str | Path | None = None,
) -> Path:
    """Build a deployable source package from the agent directory."""
    build_root = (
        Path(output_dir) if output_dir else project.root / ".build" / project.manifest.metadata.name
    )
    build_root = build_root.resolve()
    _validate_build_root(project.root, build_root)

    package_entries = _package_entries(project.root)
    compiled = project.compile()
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)

    _copy_project_tree(package_entries, build_root)
    _write_package_files(project, build_root, compiled)
    return build_root
