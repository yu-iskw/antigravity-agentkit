"""Optional Google Antigravity SDK adapters (kept separate to avoid import cycles)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from antigravity_agentkit.exceptions import CompilationError, PolicyError

ANTIGRAVITY_INSTALL_HINT = (
    "google-antigravity is not installed; install with "
    "pip install 'antigravity-agentkit[antigravity]'"
)

AskUserHandler = Callable[[Any], bool]


def _default_ask_user_handler(tool_call: Any) -> bool:
    """Deny tool calls that require interactive approval in non-interactive mode."""
    del tool_call
    return False


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


def _compile_policy_rule(rule: dict[str, Any], policies_module: Any) -> list[Any]:
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
                handler=_default_ask_user_handler,
                when=when,
                name=name,
            )
        ]
    raise PolicyError(f"Unsupported policy decision: {decision!r}")


def compile_sdk_policies(policy_dicts: list[dict[str, Any]]) -> list[Any]:
    """Convert compiled policy dicts to google.antigravity.policy objects."""
    if not policy_dicts:
        return []

    try:
        from google.antigravity import policy as policies_module
    except ImportError as exc:
        raise CompilationError(ANTIGRAVITY_INSTALL_HINT) from exc

    compiled: list[Any] = []
    for rule in policy_dicts:
        compiled.extend(_compile_policy_rule(rule, policies_module))
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
