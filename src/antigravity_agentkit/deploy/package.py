"""Build deployable source packages from compiled agent configuration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.agent import CompiledAgentConfig


def _write_package_files(
    project: AgentProject,
    build_root: Path,
    compiled: CompiledAgentConfig,
) -> None:
    """Copy manifest files and write generated runtime entrypoint."""
    data = project.data
    manifest = data.manifest

    shutil.copy2(project.root / "agent.yaml", build_root / "agent.yaml")
    system_src = project.root / manifest.spec.instructions.system
    shutil.copy2(system_src, build_root / manifest.spec.instructions.system)

    if manifest.spec.mcp:
        mcp_src = project.root / manifest.spec.mcp.file
        if mcp_src.is_file():
            shutil.copy2(mcp_src, build_root / manifest.spec.mcp.file)

    if manifest.spec.policies:
        policies_src = project.root / manifest.spec.policies.file
        if policies_src.is_file():
            shutil.copy2(policies_src, build_root / manifest.spec.policies.file)

    if manifest.spec.skills and manifest.spec.skills.local:
        for rel_path in manifest.spec.skills.local:
            src = project.root / rel_path
            dst = build_root / rel_path
            if src.is_dir():
                shutil.copytree(src, dst)

    if manifest.spec.subagents:
        for spec in manifest.spec.subagents:
            if spec.file:
                src = project.root / spec.file
                dst = build_root / spec.file
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

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
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)

    compiled = project.compile()
    _write_package_files(project, build_root, compiled)
    return build_root
