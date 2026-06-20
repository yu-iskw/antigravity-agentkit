"""Tests for runtime helpers."""

from __future__ import annotations

import asyncio
import os
import pty
import select
import signal
import subprocess
import sys
from unittest.mock import create_autospec

import pytest

from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.runtime import ReplIO, RuntimeAgent, chat_response_text


def _runtime_with_agent(agent: object) -> RuntimeAgent:
    """Build a RuntimeAgent stub that always returns the given session agent."""
    project = create_autospec(AgentProject, instance=True)
    project.create_agent.return_value = agent
    return RuntimeAgent(project)


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

    @property
    def session_open(self) -> bool:
        return self._session_open

    async def text(self) -> str:
        if not self._session_open:
            await asyncio.sleep(3600)
        return self._buffered_text


class _SessionAgent:
    """Minimal async context manager that returns a fixed chat response."""

    def __init__(self, response: _SessionBoundResponse) -> None:
        self._response = response

    async def chat(self, prompt: str) -> _SessionBoundResponse:
        del prompt
        return self._response

    async def __aenter__(self) -> _SessionAgent:
        return self

    async def __aexit__(self, *_args: object) -> None:
        self._response.close_session()


def test_run_chat_drains_response_before_session_exit() -> None:
    """run_chat must resolve text before leaving async with agent."""
    response = _SessionBoundResponse()
    runtime = _runtime_with_agent(_SessionAgent(response))

    result = asyncio.run(
        asyncio.wait_for(
            runtime.run_chat("Reply with exactly: hello from agentkit"),
            timeout=2,
        )
    )

    assert result == "hello from agentkit"
    assert not response.session_open


class _ReplSessionAgent:
    """Records chat prompts across multiple turns in one session."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def chat(self, prompt: str) -> _AsyncTextResponse:
        self.prompts.append(prompt)
        return _AsyncTextResponse()

    async def __aenter__(self) -> _ReplSessionAgent:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


def test_run_repl_multiple_turns_same_session() -> None:
    """run_repl reuses one agent session and processes multiple prompts."""
    session = _ReplSessionAgent()
    runtime = _runtime_with_agent(session)
    printed: list[str] = []
    inputs = iter(["follow up", "exit"])

    asyncio.run(
        runtime.run_repl(
            initial_prompt="hi",
            io=ReplIO(
                input_fn=lambda _prompt: next(inputs),
                print_fn=printed.append,
            ),
        )
    )

    assert session.prompts == ["hi", "follow up"]
    assert printed == ["hello from agentkit", "hello from agentkit"]


def test_run_repl_skips_empty_lines() -> None:
    """run_repl ignores blank stdin lines."""
    session = _ReplSessionAgent()
    runtime = _runtime_with_agent(session)
    inputs = iter(["", "  ", "hello", "quit"])

    asyncio.run(
        runtime.run_repl(
            io=ReplIO(
                input_fn=lambda _prompt: next(inputs),
                print_fn=lambda _text: None,
            ),
        )
    )

    assert session.prompts == ["hello"]


def test_run_repl_stops_on_eof() -> None:
    """run_repl closes the session when stdin reaches EOF."""
    session = _ReplSessionAgent()
    runtime = _runtime_with_agent(session)

    def _raise_eof(prompt: str) -> str:
        del prompt
        raise EOFError

    asyncio.run(runtime.run_repl(io=ReplIO(input_fn=_raise_eof)))

    assert not session.prompts


@pytest.mark.skipif(sys.platform == "win32", reason="PTYs are unavailable on Windows")
def test_repl_prompt_ctrl_c_exits_without_more_input() -> None:
    """Ctrl-C cancels the stdin prompt without requiring another line."""
    master_fd, slave_fd = pty.openpty()
    command = [
        sys.executable,
        "-c",
        (
            "import asyncio, signal\n"
            "from antigravity_agentkit.runtime import _read_repl_prompt\n"
            "signal.signal(signal.SIGINT, signal.default_int_handler)\n"
            "try:\n"
            "    asyncio.run(_read_repl_prompt(input))\n"
            "except KeyboardInterrupt:\n"
            "    pass\n"
        ),
    ]
    process = subprocess.Popen(  # noqa: S603
        command,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)

    try:
        readable, _, _ = select.select([master_fd], [], [], 2)
        assert readable, "REPL prompt was not written"
        assert b"You: " in os.read(master_fd, 1024)

        os.kill(process.pid, signal.SIGINT)
        process.wait(timeout=2)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master_fd)

    assert process.returncode == 0
