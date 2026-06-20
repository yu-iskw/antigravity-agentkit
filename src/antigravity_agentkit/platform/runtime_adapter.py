"""Platform Runtime adapter for Antigravity SDK agents."""

from __future__ import annotations

from typing import Any

PLATFORM_ADAPTER_FILENAME = "platform_adapter.py"
PLATFORM_ENTRYPOINT_MODULE = "platform_adapter"
PLATFORM_ENTRYPOINT_OBJECT = "platform_app"

PLATFORM_CLASS_METHODS: list[dict[str, Any]] = [
    {
        "name": "query",
        "api_mode": "",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "User message or prompt for the agent.",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "stream_query",
        "api_mode": "stream",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "User message or prompt for the agent.",
                },
            },
            "required": ["message"],
        },
    },
]


def platform_adapter_source() -> str:
    """Return ship-package platform adapter module source."""
    return '''\
"""Generated Platform Runtime adapter for Antigravity SDK agent."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

from agent import root_agent


class PlatformAgentApp:
    """Expose Antigravity SDK agent methods to Agent Platform Runtime."""

    def __init__(self, agent: Any) -> None:
        self._agent = agent

    def query(self, message: str) -> str:
        """Run a single-turn query against the agent."""
        return asyncio.run(self._run_async(message))

    def stream_query(self, message: str) -> Iterator[str]:
        """Stream query chunks (single-chunk fallback when SDK lacks streaming)."""
        yield self.query(message)

    async def _run_async(self, message: str) -> str:
        result = await self._agent.run(message)
        if isinstance(result, str):
            return result
        text = getattr(result, "text", None)
        if isinstance(text, str):
            return text
        return str(result)


platform_app = PlatformAgentApp(root_agent)
'''
