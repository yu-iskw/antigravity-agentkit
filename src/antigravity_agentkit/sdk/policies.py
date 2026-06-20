"""Compile IR policies to SDK policy objects."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from antigravity_agentkit.ir import PolicyRuleIR
from antigravity_agentkit.json_types import JsonValue
from antigravity_agentkit.sdk.capabilities import SdkCapabilities
from antigravity_agentkit.sdk.errors import ANTIGRAVITY_INSTALL_HINT, SdkCompatibilityError

AskUserHandler = Callable[[Any], bool | Awaitable[bool]]


def _default_ask_user_handler(tool_call: Any) -> bool:
    del tool_call
    return False


def _stdin_ask_user_handler(tool_call: Any) -> bool:
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


def _build_when_predicate(when: dict[str, JsonValue] | None) -> Callable[..., bool] | None:
    if not when:
        return None

    def predicate(args: dict[str, Any] | Any) -> bool:
        if not isinstance(args, dict):
            return True
        for key, expected in when.items():
            if key == "estimatedBytesProcessedGt":
                value = args.get("estimatedBytesProcessed", args.get("bytes_processed", 0))
                if not isinstance(value, (int, float)) or not isinstance(expected, (int, float)):
                    return False
                if value <= expected:
                    return False
            elif args.get(key) != expected:
                return False
        return True

    return predicate


def compile_sdk_policies(
    policies: tuple[PolicyRuleIR, ...],
    *,
    capabilities: SdkCapabilities,
    ask_user_handler: AskUserHandler | None = None,
) -> tuple[Any, ...]:
    """Compile policy IR to google.antigravity.policy objects."""
    if not policies:
        return ()

    if not capabilities.accepts_policies or capabilities.policy_module_path is None:
        raise SdkCompatibilityError(
            "The installed google-antigravity SDK cannot accept policies.",
            feature="policies",
            sdk_version=capabilities.sdk_version,
        )

    try:
        from google.antigravity import policy as policies_module
    except ImportError as exc:
        raise SdkCompatibilityError(
            ANTIGRAVITY_INSTALL_HINT,
            feature="policies",
            sdk_version=capabilities.sdk_version,
        ) from exc

    policy_api = cast("Any", policies_module)
    deny_all = policy_api.deny_all
    deny = policy_api.deny
    allow = policy_api.allow
    ask_user = policy_api.ask_user

    handler = ask_user_handler or _default_ask_user_handler
    compiled: list[Any] = []
    for rule in policies:
        if rule.default and rule.decision == "deny":
            compiled.append(deny_all())
            continue
        tool = rule.tool or "*"
        when = _build_when_predicate(rule.when)
        name = f"{rule.decision}:{tool}"
        if rule.decision == "deny":
            compiled.append(deny(tool, when=when, name=name))
        elif rule.decision == "allow":
            compiled.append(allow(tool, when=when, name=name))
        elif rule.decision in ("ask_user", "require_approval"):
            compiled.append(ask_user(tool, handler=handler, when=when, name=name))
        else:
            raise SdkCompatibilityError(
                f"Unsupported policy decision: {rule.decision!r}",
                feature="policies",
                sdk_version=capabilities.sdk_version,
            )
    return tuple(compiled)
