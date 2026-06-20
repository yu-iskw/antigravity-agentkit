"""Tests for subagent schema models."""

from __future__ import annotations

from antigravity_agentkit.schema.subagents import DelegationToolMetadata


def test_delegation_tool_metadata_tool_name() -> None:
    """Delegation tool names normalize hyphens to underscores."""
    metadata = DelegationToolMetadata(
        name="reviewer",
        description="Reviews code.",
        subagent_name="code-reviewer",
        tools=[],
        system_instructions="Review carefully.",
    )

    assert metadata.tool_name == "delegate_to_code_reviewer"
