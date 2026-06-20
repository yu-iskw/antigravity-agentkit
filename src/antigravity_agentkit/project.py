"""AgentProject orchestrates load, validate, compile, run, and package."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from antigravity_agentkit.compiler import (
    compile_from_data,
    compile_to_sdk_config,
)
from antigravity_agentkit.loader import load_agent_directory
from antigravity_agentkit.schema.agent import AgentManifest, AgentProjectData, CompiledAgentConfig
from antigravity_agentkit.sdk import get_agent_class


class AgentProject:
    """High-level interface for working with an agent directory."""

    def __init__(self, root: Path, data: AgentProjectData | None = None) -> None:
        self.root = root.resolve()
        self._data = data

    @classmethod
    def load(cls, path: str | Path) -> AgentProject:
        """Load an agent directory."""
        root = Path(path).resolve()
        data = load_agent_directory(root)
        return cls(root, data)

    @property
    def data(self) -> AgentProjectData:
        """Return loaded project data, loading lazily when needed."""
        if self._data is None:
            self._data = load_agent_directory(self.root)
        return self._data

    @property
    def manifest(self) -> AgentManifest:
        """Return parsed agent.yaml manifest."""
        return self.data.manifest

    def validate(
        self,
        *,
        production: bool = False,
        level: str = "schema",
        profile: str | None = None,
    ) -> None:
        """Validate agent manifest, security rules, skills, and policies."""
        from antigravity_agentkit.validator import (
            ValidationLevel,
            ValidationProfile,
            assert_valid_project_data,
        )

        effective_profile: ValidationProfile = profile or (  # type: ignore[assignment]
            "prod-readonly" if production else "dev-restricted"
        )
        effective_level: ValidationLevel = "full" if production else level  # type: ignore[assignment]
        assert_valid_project_data(
            self.root,
            self.data,
            level=effective_level,
            profile=effective_profile,
        )

    def compile(self, *, production: bool = False) -> CompiledAgentConfig:
        """Compile the agent directory into runtime configuration."""
        self.validate(production=production)
        return compile_from_data(self.data, _production=production)

    def create_agent(self, *, production: bool = False) -> Any:
        """Create an Antigravity SDK Agent instance."""
        compiled = self.compile(production=production)
        sdk_config = compile_to_sdk_config(compiled)
        return get_agent_class()(sdk_config)

    def _write_package_files(self, build_root: Path, compiled: CompiledAgentConfig) -> None:
        """Copy manifest files and write generated runtime entrypoint."""
        data = self.data
        manifest = data.manifest

        shutil.copy2(self.root / "agent.yaml", build_root / "agent.yaml")
        system_src = self.root / manifest.spec.instructions.system
        shutil.copy2(system_src, build_root / manifest.spec.instructions.system)

        if manifest.spec.mcp:
            mcp_src = self.root / manifest.spec.mcp.file
            if mcp_src.is_file():
                shutil.copy2(mcp_src, build_root / manifest.spec.mcp.file)

        if manifest.spec.policies:
            policies_src = self.root / manifest.spec.policies.file
            if policies_src.is_file():
                shutil.copy2(policies_src, build_root / manifest.spec.policies.file)

        if manifest.spec.skills and manifest.spec.skills.local:
            for rel_path in manifest.spec.skills.local:
                src = self.root / rel_path
                dst = build_root / rel_path
                if src.is_dir():
                    shutil.copytree(src, dst)

        if manifest.spec.subagents:
            for spec in manifest.spec.subagents:
                if spec.file:
                    src = self.root / spec.file
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

        requirements = "antigravity-agentkit\n"
        if manifest.spec.runtime.vertex.enabled:
            requirements += "google-antigravity\n"
        (build_root / "requirements.txt").write_text(requirements, encoding="utf-8")

    def package(self, output_dir: str | Path | None = None) -> Path:
        """Build a deployable source package from the agent directory."""
        build_root = (
            Path(output_dir) if output_dir else self.root / ".build" / self.manifest.metadata.name
        )
        build_root = build_root.resolve()
        if build_root.exists():
            shutil.rmtree(build_root)
        build_root.mkdir(parents=True)

        compiled = self.compile()
        self._write_package_files(build_root, compiled)
        return build_root
