"""Vertex AI Agent Engine client factory."""

from __future__ import annotations

from typing import Any, Protocol

from antigravity_agentkit.exceptions import DeployError


class AgentEngineClient(Protocol):
    """Minimal Agent Engine operations surface for testing without GCP."""

    def create(self, *, config: dict[str, Any], wait: bool = True) -> dict[str, Any]:
        """Create a reasoning engine."""
        raise NotImplementedError

    def update(
        self,
        *,
        name: str,
        config: dict[str, Any],
        wait: bool = True,
    ) -> dict[str, Any]:
        """Update an existing reasoning engine."""
        raise NotImplementedError

    def get(self, *, name: str) -> dict[str, Any]:
        """Fetch reasoning engine metadata."""
        raise NotImplementedError


def _remote_summary(remote: Any, *, name: str | None = None) -> dict[str, Any]:
    resource = getattr(remote, "api_resource", remote)
    resource_name = name
    if resource_name is None:
        resource_name = getattr(resource, "name", None) or getattr(remote, "name", None)
    display_name = getattr(resource, "display_name", None)
    return {
        "resourceName": str(resource_name) if resource_name else "",
        "displayName": str(display_name) if display_name else "",
        "raw": str(resource),
    }


class _VertexAgentEngineClient:
    """Adapter over vertexai.Client().agent_engines."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create(self, *, config: dict[str, Any], wait: bool = True) -> dict[str, Any]:
        remote = self._client.agent_engines.create(config=config)
        if wait and hasattr(remote, "wait"):
            remote.wait()
        return _remote_summary(remote)

    def update(
        self,
        *,
        name: str,
        config: dict[str, Any],
        wait: bool = True,
    ) -> dict[str, Any]:
        remote = self._client.agent_engines.update(name=name, config=config)
        if wait and hasattr(remote, "wait"):
            remote.wait()
        return _remote_summary(remote, name=name)

    def get(self, *, name: str) -> dict[str, Any]:
        remote = self._client.agent_engines.get(name=name)
        return _remote_summary(remote, name=name)


def create_vertex_agent_engine_client(project_id: str, location: str) -> AgentEngineClient:
    """Return a live Vertex AI agent engine client."""
    try:
        import vertexai  # type: ignore[import-untyped]
    except ImportError as exc:
        raise DeployError(
            "Live platform operations require the [gcp] extra: "
            "pip install 'antigravity-agentkit[gcp]'"
        ) from exc

    client = vertexai.Client(project=project_id, location=location)
    return _VertexAgentEngineClient(client)
