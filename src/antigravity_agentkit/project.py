"""AgentProject orchestrates load, validate, compile, and run."""

from __future__ import annotations

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
        effective_level: ValidationLevel = "security" if production else level  # type: ignore[assignment]
        assert_valid_project_data(
            self.root,
            self.data,
            level=effective_level,
            profile=effective_profile,
        )

    def compile(self, *, production: bool = False) -> CompiledAgentConfig:
        """Compile the agent directory into runtime configuration."""
        self.validate(production=production)
        return compile_from_data(self.data)

    def create_agent(self, *, production: bool = False, interactive: bool = False) -> Any:
        """Create an Antigravity SDK Agent instance."""
        compiled = self.compile(production=production)
        sdk_config = compile_to_sdk_config(compiled, interactive=interactive)
        return get_agent_class()(sdk_config)
