"""Compile IR subagents to SDK objects."""

from __future__ import annotations

from typing import Any

from antigravity_agentkit.ir import SubagentIR
from antigravity_agentkit.sdk.capabilities import SdkCapabilities
from antigravity_agentkit.sdk.errors import SdkCompatibilityError


def compile_sdk_subagents(
    subagents: tuple[SubagentIR, ...],
    *,
    capabilities: SdkCapabilities,
) -> tuple[Any, ...]:
    """Compile subagent IR to SDK SubagentConfig objects."""
    if not subagents:
        return ()

    if not capabilities.has_subagent_config or not capabilities.accepts_subagents:
        raise SdkCompatibilityError(
            "The installed google-antigravity SDK cannot accept static subagents.",
            feature="subagents",
            sdk_version=capabilities.sdk_version,
        )

    try:
        from google.antigravity import types
    except ImportError as exc:
        raise SdkCompatibilityError(
            "google-antigravity is required to compile subagents.",
            feature="subagents",
            sdk_version=capabilities.sdk_version,
        ) from exc

    subagent_config = getattr(types, "SubagentConfig", None)
    if subagent_config is None:
        raise SdkCompatibilityError(
            "The installed SDK does not provide SubagentConfig.",
            feature="subagents",
            sdk_version=capabilities.sdk_version,
        )

    sdk_subagents: list[Any] = []
    for entry in subagents:
        kwargs: dict[str, Any] = {
            "name": entry.name,
            "description": entry.description or f"Subagent {entry.name}",
            "system_instructions": entry.system_instructions or "",
        }
        if entry.tools:
            kwargs["tools"] = list(entry.tools)
        sdk_subagents.append(subagent_config(**kwargs))
    return tuple(sdk_subagents)
