"""Tests for runtime helpers."""

from __future__ import annotations

import asyncio

from antigravity_agentkit.runtime import chat_response_text


class _AsyncTextResponse:
    async def text(self) -> str:
        return "hello from agentkit"


class _SyncTextResponse:
    def text(self) -> str:
        return "sync text"


def test_chat_response_text_awaits_async_text() -> None:
    """chat_response_text drains async ChatResponse.text()."""
    result = asyncio.run(chat_response_text(_AsyncTextResponse()))

    assert result == "hello from agentkit"


def test_chat_response_text_handles_sync_text() -> None:
    """chat_response_text accepts a synchronous text() return value."""
    result = asyncio.run(chat_response_text(_SyncTextResponse()))

    assert result == "sync text"


def test_chat_response_text_falls_back_to_str() -> None:
    """chat_response_text uses str() when no text() method exists."""
    result = asyncio.run(chat_response_text({"answer": "plain"}))

    assert "answer" in result


class _SessionBoundResponse:
    """Simulates SDK ChatResponse that blocks after its agent session closes."""

    def __init__(self) -> None:
        self._session_open = True
        self._buffered_text = "hello from agentkit"

    def close_session(self) -> None:
        self._session_open = False

    async def text(self) -> str:
        if not self._session_open:
            await asyncio.sleep(3600)
        return self._buffered_text


class _SessionAgent:
    def __init__(self, response: _SessionBoundResponse) -> None:
        self._response = response

    async def chat(self, _prompt: str) -> _SessionBoundResponse:
        return self._response

    async def __aenter__(self) -> _SessionAgent:
        return self

    async def __aexit__(self, *_args: object) -> None:
        self._response.close_session()


def test_run_chat_drains_response_before_session_exit() -> None:
    """run_chat must resolve text before leaving async with agent."""
    from antigravity_agentkit.runtime import RuntimeAgent

    response = _SessionBoundResponse()
    runtime = RuntimeAgent.__new__(RuntimeAgent)
    runtime._project = type(
        "_P",
        (),
        {
            "create_agent": staticmethod(lambda **_: _SessionAgent(response)),
        },
    )()

    result = asyncio.run(
        asyncio.wait_for(
            runtime.run_chat("Reply with exactly: hello from agentkit"),
            timeout=2,
        )
    )

    assert result == "hello from agentkit"
    assert not response._session_open
