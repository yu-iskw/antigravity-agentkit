"""Local runtime helpers wrapping Antigravity SDK Agent."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from antigravity_agentkit.sdk import compile_sdk_policies

if TYPE_CHECKING:
    from antigravity_agentkit.project import AgentProject


class RuntimeAgent:
    """Thin wrapper around AgentProject.create_agent() for local chat."""

    def __init__(self, project: AgentProject) -> None:
        self._project = project

    @property
    def project(self) -> AgentProject:
        """Return the underlying AgentProject."""
        return self._project

    @classmethod
    def from_directory(
        cls,
        path: str | Path,
        *,
        production: bool = False,
    ) -> RuntimeAgent:
        """Load an agent directory and return a RuntimeAgent."""
        from antigravity_agentkit.project import AgentProject

        project = AgentProject.load(path)
        if production:
            project.validate(production=True)
        return cls(project)

    async def run_chat(self, prompt: str, *, production: bool = False) -> Any:
        """Run a single chat turn against the compiled agent."""
        agent = self._project.create_agent(production=production)
        async with agent:
            return await agent.chat(prompt)


__all__ = ["RuntimeAgent", "compile_sdk_policies"]
