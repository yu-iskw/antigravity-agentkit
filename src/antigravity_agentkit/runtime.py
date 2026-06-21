"""Local runtime helpers wrapping Antigravity SDK Agent."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from antigravity_agentkit.ir import CompiledAgentIR
from antigravity_agentkit.operator_auth import (
    operator_credentials_context,
    resolve_impersonate_target,
)

if TYPE_CHECKING:
    from antigravity_agentkit.project import AgentProject

_EXIT_COMMANDS = frozenset({"exit", "quit"})
_DEBUG_TRUNCATE = 200
ChunkKind = Literal["text", "thought", "tool_call", "tool_result"]


@dataclass(frozen=True)
class ChatDisplay:
    """Controls streaming assistant text and debug loop status output."""

    stream: bool = False
    debug: bool = False

    @classmethod
    def from_cli(cls, *, stream: bool | None, debug: bool) -> ChatDisplay:
        """Resolve CLI flags with TTY-default streaming."""
        effective_stream = sys.stdout.isatty() if stream is None else stream
        return cls(stream=effective_stream, debug=debug)


@dataclass(frozen=True)
class ReplIO:
    """Injectable I/O hooks for ``run_repl`` (CLI and tests)."""

    input_fn: Callable[[str], str] = input
    print_fn: Callable[[str], None] | None = None


def _default_print(text: str) -> None:
    print(text, flush=True)


def _stream_write_out(text: str) -> None:
    print(text, end="", flush=True)


def _default_debug_print(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


def _format_tool_call(chunk: Any) -> str:
    name = getattr(chunk, "name", "unknown")
    args = getattr(chunk, "args", None)
    if args is None:
        args = getattr(chunk, "arguments", None)
    return f"[tool] call {name}({args})"


def _format_tool_result(chunk: Any) -> str:
    result = getattr(chunk, "result", None)
    if result is None:
        result = getattr(chunk, "content", chunk)
    text = str(result)
    if len(text) > _DEBUG_TRUNCATE:
        text = f"{text[:_DEBUG_TRUNCATE]}..."
    return f"[tool] result {text}"


def _classify_chunk(chunk: Any) -> ChunkKind | None:
    """Classify SDK stream chunks; falls back to class name when types are unavailable."""
    try:
        from google.antigravity.types import Text, Thought, ToolCall, ToolResult

        if isinstance(chunk, Text):
            return "text"
        if isinstance(chunk, Thought):
            return "thought"
        if isinstance(chunk, ToolCall):
            return "tool_call"
        if isinstance(chunk, ToolResult):
            return "tool_result"
    except ImportError:
        # google-antigravity is optional; fall back to class-name matching below.
        pass

    name = type(chunk).__name__
    if name == "Text":
        return "text"
    if name == "Thought":
        return "thought"
    if name == "ToolCall":
        return "tool_call"
    if name == "ToolResult":
        return "tool_result"
    return None


async def chat_response_text(response: Any) -> str:
    """Return aggregated assistant text from an SDK ``ChatResponse``."""
    get_text = getattr(response, "text", None)
    if get_text is None:
        return str(response)
    text = get_text()
    if hasattr(text, "__await__"):
        return await text
    return str(text)


async def consume_chat_response(
    response: Any,
    display: ChatDisplay,
    *,
    write_out: Callable[[str], None] | None = None,
    write_debug: Callable[[str], None] | None = None,
) -> str:
    """Stream or debug-print a ChatResponse, then return aggregated assistant text."""
    effective_write_out = write_out or (_stream_write_out if display.stream else _default_print)
    effective_write_debug = write_debug or _default_debug_print

    if not display.stream and not display.debug:
        return await chat_response_text(response)

    chunks_attr = getattr(response, "chunks", None)
    if chunks_attr is None:
        if display.stream:
            effective_write_debug("debug: streaming unavailable")
        full_text = await chat_response_text(response)
        if display.stream and full_text:
            effective_write_out(full_text)
            effective_write_out("\n")
        return full_text

    streamed_text = False
    async for chunk in chunks_attr:
        kind = _classify_chunk(chunk)
        if kind == "text" and display.stream:
            effective_write_out(getattr(chunk, "text", ""))
            streamed_text = True
        elif kind == "thought" and display.debug:
            thought_text = getattr(chunk, "text", "")
            effective_write_debug(f"[thought] {thought_text}")
        elif kind == "tool_call" and display.debug:
            effective_write_debug(_format_tool_call(chunk))
        elif kind == "tool_result" and display.debug:
            effective_write_debug(_format_tool_result(chunk))

    if display.stream and streamed_text:
        effective_write_out("\n")

    return await chat_response_text(response)


async def _agent_chat_turn(
    agent: Any,
    prompt: str,
    *,
    display: ChatDisplay = ChatDisplay(),
    write_out: Callable[[str], None] | None = None,
) -> str:
    """Run one chat turn and drain response text before the session closes."""
    response = await agent.chat(prompt)
    return await consume_chat_response(response, display, write_out=write_out)


async def run_single_chat_turn(
    agent: Any,
    message: str,
    *,
    display: ChatDisplay = ChatDisplay(),
) -> str:
    """Run one chat turn inside the SDK async session context."""
    async with agent:
        return await _agent_chat_turn(agent, message, display=display)


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
        display: ChatDisplay = ChatDisplay(),
    ) -> str:
        """Run a single chat turn and return aggregated assistant text."""
        impersonate = resolve_impersonate_target(flag=impersonate_service_account)
        with operator_credentials_context(impersonate):
            agent = self._project.create_agent(production=production, interactive=interactive)
            return await run_single_chat_turn(agent, prompt, display=display)

    async def run_repl(  # noqa: PLR0913
        self,
        *,
        production: bool = False,
        interactive: bool = False,
        impersonate_service_account: str | None = None,
        initial_prompt: str | None = None,
        io: ReplIO | None = None,
        display: ChatDisplay = ChatDisplay(),
    ) -> None:
        """Run a multi-turn stdin chat loop until exit, quit, or EOF."""
        impersonate = resolve_impersonate_target(flag=impersonate_service_account)
        repl_io = io or ReplIO()
        output = repl_io.print_fn or _default_print

        async def _turn(agent: Any, prompt: str) -> None:
            result = await _agent_chat_turn(agent, prompt, display=display)
            if not display.stream:
                output(result)

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


def create_agent_from_ir(
    ir: CompiledAgentIR,
    *,
    project_root: str | Path,
    interactive: bool = False,
    loaded_skills: dict[str, Any] | None = None,
) -> Any:
    """Create an Antigravity SDK Agent from compiled IR (requires [antigravity])."""
    from antigravity_agentkit.sdk.runtime import create_agent_from_ir as _create_agent_from_ir

    return _create_agent_from_ir(
        ir,
        project_root=project_root,
        interactive=interactive,
        loaded_skills=loaded_skills,
    )


def create_agent_from_project(
    project: AgentProject,
    *,
    production: bool = False,
    interactive: bool = False,
) -> Any:
    """Compile a project and return an Antigravity SDK Agent (requires [antigravity])."""
    ir = project.compile(production=production)
    return create_agent_from_ir(
        ir,
        project_root=project.root,
        interactive=interactive,
        loaded_skills=project.data.skills,
    )


def create_sdk_config_from_ir(
    ir: CompiledAgentIR,
    *,
    project_root: str | Path,
    interactive: bool = False,
    loaded_skills: dict[str, Any] | None = None,
) -> Any:
    """Create a LocalAgentConfig from compiled IR (requires [antigravity])."""
    from antigravity_agentkit.sdk.runtime import create_sdk_config_from_ir as _create_sdk_config

    return _create_sdk_config(
        ir,
        project_root=project_root,
        interactive=interactive,
        loaded_skills=loaded_skills,
    )


def create_agent_from_ir_file(
    path: str | Path,
    *,
    project_root: str | Path = ".",
) -> Any:
    """Create an Antigravity SDK Agent from serialized IR JSON (requires [antigravity])."""
    from antigravity_agentkit.sdk.runtime import create_agent_from_ir_file as _create_from_file

    return _create_from_file(path, project_root=project_root)


__all__ = [
    "ChatDisplay",
    "ReplIO",
    "RuntimeAgent",
    "chat_response_text",
    "consume_chat_response",
    "create_agent_from_ir",
    "create_agent_from_ir_file",
    "create_agent_from_project",
    "create_sdk_config_from_ir",
    "run_single_chat_turn",
]
