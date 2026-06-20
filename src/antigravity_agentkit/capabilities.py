"""Capabilities compilation for Antigravity SDK builtin tool gating."""

from __future__ import annotations

from typing import Any

from antigravity_agentkit.schema.agent import CapabilitiesConfig

# Manifest tool names → google.antigravity.types.BuiltinTools attribute names.
TOOL_MAP: dict[str, str] = {
    "list_directory": "LIST_DIR",
    "search_directory": "SEARCH_DIR",
    "find_file": "FIND_FILE",
    "view_file": "VIEW_FILE",
    "create_file": "CREATE_FILE",
    "edit_file": "EDIT_FILE",
    "run_command": "RUN_COMMAND",
    "ask_question": "ASK_QUESTION",
    "start_subagent": "START_SUBAGENT",
    "generate_image": "GENERATE_IMAGE",
    "search_web": "SEARCH_WEB",
    "finish": "FINISH",
}

LOCKED_MODE_DISABLED_TOOLS = ("run_command", "create_file", "edit_file")


def compile_capabilities_ir(
    capabilities: CapabilitiesConfig,
    *,
    has_subagents: bool,
) -> dict[str, Any]:
    """Compile agent.yaml capabilities into serializable IR for the SDK emitter."""
    enable_subagents = capabilities.enable_subagents
    if enable_subagents is None:
        enable_subagents = has_subagents

    enabled_tools = list(capabilities.enabled_tools)
    disabled_tools = list(capabilities.disabled_tools)

    if not enabled_tools and not disabled_tools and capabilities.mode == "locked":
        disabled_tools = list(LOCKED_MODE_DISABLED_TOOLS)

    return {
        "mode": capabilities.mode,
        "enableSubagents": enable_subagents,
        "enabledTools": enabled_tools,
        "disabledTools": disabled_tools,
    }


def _resolve_builtin_tool(tool_name: str, builtin_tools: Any) -> Any:
    """Map a manifest tool name to a BuiltinTools enum value when known."""
    attr_name = TOOL_MAP.get(tool_name)
    if attr_name is None:
        return tool_name
    return getattr(builtin_tools, attr_name)


def capabilities_ir_is_default(cap_ir: dict[str, Any]) -> bool:
    """Return True when capabilities IR matches SDK defaults (no emit needed)."""
    return (
        cap_ir.get("mode") == "restricted"
        and not cap_ir.get("enableSubagents")
        and not cap_ir.get("enabledTools")
        and not cap_ir.get("disabledTools")
    )


def try_compile_sdk_capabilities(cap_ir: dict[str, Any]) -> Any | None:
    """Compile capabilities IR to SDK CapabilitiesConfig when SDK is available."""
    if capabilities_ir_is_default(cap_ir):
        return None

    try:
        from google.antigravity import types
    except ImportError:
        return None

    builtin_tools = getattr(types, "BuiltinTools", None)
    capabilities_config = getattr(types, "CapabilitiesConfig", None)
    if builtin_tools is None or capabilities_config is None:
        return None

    kwargs: dict[str, Any] = {}
    enable_subagents = cap_ir.get("enableSubagents")
    if enable_subagents is True:
        kwargs["enable_subagents"] = True
    elif enable_subagents is False:
        kwargs["enable_subagents"] = False

    enabled = cap_ir.get("enabledTools") or []
    if enabled:
        kwargs["enabled_tools"] = [_resolve_builtin_tool(name, builtin_tools) for name in enabled]

    disabled = cap_ir.get("disabledTools") or []
    if disabled:
        kwargs["disabled_tools"] = [_resolve_builtin_tool(name, builtin_tools) for name in disabled]

    if kwargs:
        return capabilities_config(**kwargs)

    mode = cap_ir.get("mode", "restricted")
    if mode == "open":
        return capabilities_config()

    return None
