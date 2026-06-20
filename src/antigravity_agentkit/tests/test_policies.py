"""Tests for policies.yaml parsing and compilation."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_agentkit.exceptions import ValidationError
from antigravity_agentkit.policies import (
    compile_policy_dicts,
    parse_policies_dict,
    parse_policies_yaml,
    resolve_tool_decision,
)
from antigravity_agentkit.schema.policies import PolicyDocument


def test_mcp_policies_default_deny(mcp_agent_dir: Path) -> None:
    """mcp example policies use default deny."""
    doc = parse_policies_yaml(mcp_agent_dir / "policies.yaml")

    assert doc.default == "deny"


def test_resolve_tool_decision_default_deny() -> None:
    """Unknown tools fall through to default deny."""
    doc = PolicyDocument.model_validate(
        {
            "default": "deny",
            "allow": [{"tool": "view_file"}],
        }
    )

    assert resolve_tool_decision("view_file", doc) == "allow"
    assert resolve_tool_decision("run_command", doc) == "deny"
    assert resolve_tool_decision("unknown_tool", doc) == "deny"


def test_resolve_tool_decision_precedence() -> None:
    """Deny takes precedence over allow for the same tool."""
    doc = PolicyDocument.model_validate(
        {
            "default": "allow",
            "allow": [{"tool": "write_file"}],
            "deny": [{"tool": "write_file"}],
        }
    )

    assert resolve_tool_decision("write_file", doc) == "deny"


def test_rejects_unknown_top_level_keys() -> None:
    """Unknown policies.yaml keys are rejected."""
    with pytest.raises(ValidationError, match="Unknown policies.yaml keys"):
        parse_policies_dict({"default": "deny", "customSection": []})


def test_rejects_non_list_policy_section() -> None:
    """Policy sections must be lists."""
    with pytest.raises(ValidationError, match="must be a list"):
        parse_policies_dict({"default": "deny", "allow": "view_file"})


def test_rejects_policy_entry_without_tool() -> None:
    """Each policy entry must include a tool field."""
    with pytest.raises(ValidationError, match="missing required 'tool'"):
        parse_policies_dict({"default": "deny", "deny": [{"when": {"risk": "high"}}]})


def test_compile_policy_dicts_includes_default_deny() -> None:
    """Default deny compiles to a catch-all deny rule."""
    doc = PolicyDocument.model_validate(
        {
            "default": "deny",
            "allow": [{"tool": "view_file"}],
            "deny": [{"tool": "run_command"}],
        }
    )
    compiled = compile_policy_dicts(doc)

    assert any(
        item.get("tool") == "run_command" and item.get("decision") == "deny" for item in compiled
    )
    assert any(
        item.get("tool") == "*" and item.get("decision") == "deny" and item.get("default")
        for item in compiled
    )


ESTIMATED_BYTES_APPROVAL_THRESHOLD = 10_000_000_000


def test_compile_policy_dicts_ask_user_and_approval() -> None:
    """askUser and requireApproval rules compile with when clauses."""
    doc = parse_policies_dict(
        {
            "askUser": [{"tool": "mcp.clock.echo", "when": {"risk": "medium"}}],
            "requireApproval": [
                {
                    "tool": "mcp.bigquery.run_query",
                    "when": {
                        "estimatedBytesProcessedGt": ESTIMATED_BYTES_APPROVAL_THRESHOLD,
                    },
                }
            ],
        }
    )
    compiled = compile_policy_dicts(doc)

    ask_user = next(item for item in compiled if item["decision"] == "ask_user")
    assert ask_user["tool"] == "mcp.clock.echo"
    assert ask_user["when"]["risk"] == "medium"

    require_approval = next(item for item in compiled if item["decision"] == "require_approval")
    assert (
        require_approval["when"]["estimatedBytesProcessedGt"] == ESTIMATED_BYTES_APPROVAL_THRESHOLD
    )


def test_rejects_unknown_policy_condition() -> None:
    """Unknown when-clause operators must not bypass strict schema validation."""
    with pytest.raises(ValidationError, match="lengthGt"):
        parse_policies_dict(
            {
                "requireApproval": [
                    {"tool": "mcp.clock.echo", "when": {"lengthGt": 100}},
                ]
            }
        )
