"""Local runtime helpers wrapping Antigravity SDK Agent."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from antigravity_agentkit.operator_auth import (
    operator_credentials_context,
    resolve_impersonate_target,
)
from antigravity_agentkit.sdk import compile_sdk_policies

if TYPE_CHECKING:
    from antigravity_agentkit.project import AgentProject

_EXIT_COMMANDS = frozenset({"exit", "quit"})


@dataclass(frozen=True)
class ReplIO:
    """Injectable I/O hooks for ``run_repl`` (CLI and tests)."""

    input_fn: Callable[[str], str] = input
    print_fn: Callable[[str], None] | None = None


def _default_print(text: str) -> None:
    print(text, flush=True)


async def chat_response_text(response: Any) -> str:
    """Return aggregated assistant text from an SDK ``ChatResponse``."""
    get_text = getattr(response, "text", None)
    if get_text is None:
        return str(response)
    text = get_text()
    if hasattr(text, "__await__"):
        return await text
    return str(text)


async def _agent_chat_turn(agent: Any, prompt: str) -> str:
    """Run one chat turn and drain response text before the session closes."""
    response = await agent.chat(prompt)
    return await chat_response_text(response)


async def _read_stdin_prompt() -> str:
    """Read stdin without leaving a blocking executor thread on cancellation."""
    loop = asyncio.get_running_loop()
    try:
        stdin_fd = sys.stdin.fileno()
        was_blocking = os.get_blocking(stdin_fd)
        os.set_blocking(stdin_fd, False)
    except (AttributeError, OSError):
        return input("You: ").strip()

    result: asyncio.Future[str] = loop.create_future()
    line = bytearray()

    def _finish_line() -> None:
        encoding = sys.stdin.encoding or "utf-8"
        errors = sys.stdin.errors or "strict"
        result.set_result(line.decode(encoding, errors))

    def _read_ready_line() -> None:
        if result.done():
            return
        try:
            chunk = os.read(stdin_fd, 1)
        except BlockingIOError:
            return
        except OSError as exc:
            result.set_exception(exc)
            return
        if not chunk:
            if line:
                _finish_line()
            else:
                result.set_exception(EOFError())
            return
        if chunk == b"\n":
            _finish_line()
            return
        line.extend(chunk)

    try:
        loop.add_reader(stdin_fd, _read_ready_line)
    except (AttributeError, OSError, NotImplementedError):
        with contextlib.suppress(OSError):
            os.set_blocking(stdin_fd, was_blocking)
        return input("You: ").strip()

    try:
        print("You: ", end="", flush=True)
        return (await result).strip()
    finally:
        loop.remove_reader(stdin_fd)
        with contextlib.suppress(OSError):
            os.set_blocking(stdin_fd, was_blocking)


async def _read_repl_prompt(input_fn: Callable[[str], str]) -> str:
    """Read a REPL prompt without blocking the event loop on stdin."""
    if input_fn is input:
        return await _read_stdin_prompt()
    return input_fn("You: ").strip()


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
                return await _agent_chat_turn(agent, prompt)

    async def run_repl(
        self,
        *,
        production: bool = False,
        interactive: bool = False,
        impersonate_service_account: str | None = None,
        initial_prompt: str | None = None,
        io: ReplIO | None = None,
    ) -> None:
        """Run a multi-turn stdin chat loop until exit, quit, or EOF."""
        impersonate = resolve_impersonate_target(flag=impersonate_service_account)
        repl_io = io or ReplIO()
        output = repl_io.print_fn or _default_print

        async def _turn(agent: Any, prompt: str) -> None:
            output(await _agent_chat_turn(agent, prompt))

        with operator_credentials_context(impersonate):
            agent = self._project.create_agent(production=production, interactive=interactive)
            async with agent:
                if initial_prompt:
                    await _turn(agent, initial_prompt)
                while True:
                    try:
                        prompt = await _read_repl_prompt(repl_io.input_fn)
                    except EOFError:
                        break
                    if not prompt:
                        continue
                    if prompt.lower() in _EXIT_COMMANDS:
                        break
                    await _turn(agent, prompt)


__all__ = ["ReplIO", "RuntimeAgent", "chat_response_text", "compile_sdk_policies"]
