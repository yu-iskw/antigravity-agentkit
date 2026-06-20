"""Optional Google Antigravity SDK adapters (kept separate to avoid import cycles)."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from antigravity_agentkit.capabilities import try_compile_sdk_capabilities
from antigravity_agentkit.exceptions import CompilationError, PolicyError
from antigravity_agentkit.mcp import try_compile_mcp_sdk_objects_from_compiled
from antigravity_agentkit.schema.agent import CompiledAgentConfig
from antigravity_agentkit.subagents import sdk_subagents_supported, try_compile_sdk_subagents

ANTIGRAVITY_INSTALL_HINT = (
    "google-antigravity is not installed; install with "
    "pip install 'antigravity-agentkit[antigravity]'"
)

AskUserHandler = Callable[[Any], bool | Awaitable[bool]]


def _default_ask_user_handler(tool_call: Any) -> bool:
    """Deny tool calls that require interactive approval in non-interactive mode."""
    del tool_call
    return False


def _stdin_ask_user_handler(tool_call: Any) -> bool:
    """Prompt on stdin for tool approval when SDK interactive helper is unavailable."""
    tool_name = getattr(tool_call, "name", "unknown")
    answer = input(f"Approve tool {tool_name}? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def resolve_ask_user_handler(*, interactive: bool) -> AskUserHandler:
    """Return the ask-user handler for the current run mode."""
    if not interactive:
        return _default_ask_user_handler

    try:
        from google.antigravity.utils import interactive as interactive_utils

        return interactive_utils.ask_user_handler
    except ImportError:
        return _stdin_ask_user_handler


def _build_when_predicate(when: dict[str, Any] | None) -> Callable[..., bool] | None:
    """Build a simple predicate from a policy when-clause."""
    if not when:
        return None

    def predicate(args: dict[str, Any] | Any) -> bool:
        if not isinstance(args, dict):
            return True
        for key, expected in when.items():
            if key == "estimatedBytesProcessedGt":
                value = args.get("estimatedBytesProcessed", args.get("bytes_processed", 0))
                if not isinstance(value, (int, float)) or value <= expected:
                    return False
            elif args.get(key) != expected:
                return False
        return True

    return predicate


def _compile_policy_rule(
    rule: dict[str, Any],
    policies_module: Any,
    *,
    ask_user_handler: AskUserHandler,
) -> list[Any]:
    """Compile a single policy dict into SDK policy object(s)."""
    if rule.get("default") and rule.get("decision") == "deny":
        return [policies_module.deny_all()]

    tool = rule["tool"]
    decision = rule.get("decision", "allow")
    when = _build_when_predicate(rule.get("when"))
    name = f"{decision}:{tool}"

    if decision == "deny":
        return [policies_module.deny(tool, when=when, name=name)]
    if decision == "allow":
        return [policies_module.allow(tool, when=when, name=name)]
    if decision in ("ask_user", "require_approval"):
        return [
            policies_module.ask_user(
                tool,
                handler=ask_user_handler,
                when=when,
                name=name,
            )
        ]
    raise PolicyError(f"Unsupported policy decision: {decision!r}")


def compile_sdk_policies(
    policy_dicts: list[dict[str, Any]],
    *,
    ask_user_handler: AskUserHandler | None = None,
) -> list[Any]:
    """Convert compiled policy dicts to google.antigravity.policy objects."""
    if not policy_dicts:
        return []

    try:
        from google.antigravity import policy as policies_module
    except ImportError as exc:
        raise CompilationError(ANTIGRAVITY_INSTALL_HINT) from exc

    handler = ask_user_handler or _default_ask_user_handler
    compiled: list[Any] = []
    for rule in policy_dicts:
        compiled.extend(_compile_policy_rule(rule, policies_module, ask_user_handler=handler))
    return compiled


def get_local_agent_config_class() -> type[Any]:
    """Return LocalAgentConfig when the Antigravity SDK is installed."""
    try:
        from google.antigravity import LocalAgentConfig
    except ImportError as exc:
        raise CompilationError(ANTIGRAVITY_INSTALL_HINT) from exc
    return LocalAgentConfig


def get_agent_class() -> type[Any]:
    """Return Agent when the Antigravity SDK is installed."""
    try:
        from google.antigravity import Agent
    except ImportError as exc:
        raise CompilationError(ANTIGRAVITY_INSTALL_HINT) from exc
    return Agent


def compile_to_sdk_config_from_compiled(
    compiled: CompiledAgentConfig,
    *,
    interactive: bool = False,
) -> Any:
    """Convert CompiledAgentConfig to Antigravity LocalAgentConfig when SDK is available."""
    local_agent_config = get_local_agent_config_class()
    ask_user_handler = resolve_ask_user_handler(interactive=interactive)

    kwargs: dict[str, Any] = {
        "system_instructions": compiled.system_instructions,
        "vertex": compiled.vertex.get("enabled", False),
    }
    if compiled.vertex.get("project"):
        kwargs["project"] = compiled.vertex["project"]
    if compiled.vertex.get("location"):
        kwargs["location"] = compiled.vertex["location"]
    if compiled.model:
        kwargs["model"] = compiled.model
    if compiled.mcp_servers:
        kwargs["mcp_servers"] = try_compile_mcp_sdk_objects_from_compiled(compiled.mcp_servers)
    if compiled.skills_paths:
        signature = inspect.signature(local_agent_config)
        parameters = signature.parameters.values()
        accepts_skills_paths = "skills_paths" in signature.parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters
        )
        if not accepts_skills_paths:
            raise CompilationError(
                "The installed google-antigravity SDK cannot accept skills_paths; "
                "install a compatible SDK version."
            )
        kwargs["skills_paths"] = list(compiled.skills_paths)
    if compiled.runtime_tools:
        kwargs["tools"] = list(compiled.runtime_tools)

    capabilities = try_compile_sdk_capabilities(compiled.capabilities)
    if capabilities is not None:
        kwargs["capabilities"] = capabilities

    if compiled.capabilities.get("enableSubagents") and compiled.subagents:
        if not sdk_subagents_supported():
            raise CompilationError(
                "The installed google-antigravity SDK does not support static subagents; "
                "install a version that provides google.antigravity.types.SubagentConfig."
            )
        sdk_subagents = try_compile_sdk_subagents(compiled.subagents)
        signature = inspect.signature(local_agent_config)
        parameters = signature.parameters.values()
        accepts_subagents = "subagents" in signature.parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters
        )
        if not accepts_subagents:
            raise CompilationError(
                "The installed google-antigravity SDK cannot accept static subagents; "
                "install a compatible SDK version."
            )
        kwargs["subagents"] = sdk_subagents

    if compiled.policies:
        kwargs["policies"] = compile_sdk_policies(
            compiled.policies,
            ask_user_handler=ask_user_handler,
        )

    return local_agent_config(**kwargs)
