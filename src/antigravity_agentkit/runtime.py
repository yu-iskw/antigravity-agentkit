"""Local runtime helpers wrapping Antigravity SDK Agent."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from antigravity_agentkit.operator_auth import (
    operator_credentials_context,
    resolve_impersonate_target,
)
from antigravity_agentkit.sdk import compile_sdk_policies

if TYPE_CHECKING:
    from antigravity_agentkit.project import AgentProject


async def chat_response_text(response: Any) -> str:
    """Return aggregated assistant text from an SDK ``ChatResponse``."""
    get_text = getattr(response, "text", None)
    if get_text is None:
        return str(response)
    text = get_text()
    if hasattr(text, "__await__"):
        return await text
    return str(text)


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

    async def run_chat(
        self,
        prompt: str,
        *,
        production: bool = False,
        interactive: bool = False,
        impersonate_service_account: str | None = None,
    ) -> str:
        """Run a single chat turn and return aggregated assistant text."""
        impersonate = resolve_impersonate_target(flag=impersonate_service_account)
        with operator_credentials_context(impersonate):
            agent = self._project.create_agent(production=production, interactive=interactive)
            async with agent:
                response = await agent.chat(prompt)
                # Drain before session exit; ChatResponse.text() hangs after __aexit__.
                return await chat_response_text(response)


__all__ = ["RuntimeAgent", "chat_response_text", "compile_sdk_policies"]
