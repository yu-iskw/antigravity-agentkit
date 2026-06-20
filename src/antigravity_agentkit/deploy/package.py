"""Build deployable source packages from compiled agent configuration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.agent import CompiledAgentConfig


def _package_paths(project_root: Path, build_root: Path, relative_path: str) -> tuple[Path, Path]:
    """Resolve a project-relative source and its package destination safely."""
    path = Path(relative_path)
    if path.is_absolute():
        raise DeployError(f"Package source path must be relative: {relative_path}")

    source = (project_root / path).resolve()
    destination = (build_root / path).resolve()
    if not source.is_relative_to(project_root):
        raise DeployError(f"Package source path escapes the agent directory: {relative_path}")
    if not destination.is_relative_to(build_root):
        raise DeployError(f"Package destination path escapes the build directory: {relative_path}")
    return source, destination


def _copy_project_file(project_root: Path, build_root: Path, relative_path: str) -> None:
    """Copy one project file into the package, creating parent directories."""
    source, destination = _package_paths(project_root, build_root, relative_path)
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
    """Copy manifest files and write generated runtime entrypoint."""
    data = project.data
    manifest = data.manifest

    _copy_project_file(project.root, build_root, "agent.yaml")
    _copy_project_file(project.root, build_root, manifest.spec.instructions.system)

    if manifest.spec.mcp:
        mcp_src, _ = _package_paths(project.root, build_root, manifest.spec.mcp.file)
        if mcp_src.is_file():
            _copy_project_file(project.root, build_root, manifest.spec.mcp.file)

    if manifest.spec.policies:
        policies_src, _ = _package_paths(project.root, build_root, manifest.spec.policies.file)
        if policies_src.is_file():
            _copy_project_file(project.root, build_root, manifest.spec.policies.file)

    if manifest.spec.skills and manifest.spec.skills.local:
        for rel_path in manifest.spec.skills.local:
            src, dst = _package_paths(project.root, build_root, rel_path)
            if src.is_dir():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst)

    if manifest.spec.subagents:
        for spec in manifest.spec.subagents:
            if spec.file:
                _copy_project_file(project.root, build_root, spec.file)

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

    compiled = project.compile()
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)

    _write_package_files(project, build_root, compiled)
    return build_root
