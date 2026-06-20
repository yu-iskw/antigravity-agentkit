"""Tests for capabilities compilation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from antigravity_agentkit.capabilities import (
    LOCKED_MODE_DISABLED_TOOLS,
    capabilities_ir_is_default,
    compile_capabilities_ir,
)
from antigravity_agentkit.compiler import compile_from_data
from antigravity_agentkit.loader import load_agent_directory
from antigravity_agentkit.schema.agent import CapabilitiesConfig


def test_locked_mode_adds_disabled_tools() -> None:
    """Locked mode disables dangerous builtin tools when lists are omitted."""
    cap_ir = compile_capabilities_ir(CapabilitiesConfig(mode="locked"), has_subagents=False)

    assert cap_ir["disabledTools"] == list(LOCKED_MODE_DISABLED_TOOLS)


def test_subagents_auto_enable() -> None:
    """Subagents auto-enable when enableSubagents is unset."""
    cap_ir = compile_capabilities_ir(CapabilitiesConfig(), has_subagents=True)

    assert cap_ir["enableSubagents"] is True


def test_default_capabilities_ir_is_default() -> None:
    """Restricted mode without lists matches SDK defaults."""
    cap_ir = compile_capabilities_ir(CapabilitiesConfig(), has_subagents=False)

    assert capabilities_ir_is_default(cap_ir)


def test_enable_subagents_false_disables_runtime_subagents(subagents_agent_dir: Path) -> None:
    """Explicit enableSubagents false omits delegation tools and prompt injection."""
    data = load_agent_directory(subagents_agent_dir)
    data.manifest.spec.runtime.capabilities.enable_subagents = False
    compiled = compile_from_data(data)

    assert compiled.capabilities["enableSubagents"] is False
    assert compiled.subagents
    tool_names = [tool["name"] for tool in compiled.tools if isinstance(tool, dict)]
    assert "delegate_to_proofreader" not in tool_names
    assert "## Available Subagents" not in compiled.system_instructions


def test_open_mode_emits_sdk_capabilities() -> None:
    """Open mode emits an explicit SDK CapabilitiesConfig when lists are empty."""
    from antigravity_agentkit.capabilities import try_compile_sdk_capabilities

    cap_ir = compile_capabilities_ir(
        CapabilitiesConfig(mode="open"),
        has_subagents=False,
    )

    if importlib.util.find_spec("google.antigravity") is None:
        pytest.skip("google-antigravity not installed")

    sdk_cap = try_compile_sdk_capabilities(cap_ir)
    assert sdk_cap is not None
    assert sdk_cap.enabled_tools is None
    assert sdk_cap.disabled_tools is None
