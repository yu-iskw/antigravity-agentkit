"""Tests for policies.yaml schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from antigravity_agentkit.schema.policies import PolicyDocument, PolicyRule
from antigravity_agentkit.tests.schema.conftest import minimal_policy_dict


def test_policy_rule_rejects_blank_tool() -> None:
    """Policy tool identifiers must not be blank."""
    with pytest.raises(ValidationError, match="blank"):
        PolicyRule.model_validate({"tool": "   "})


def test_policy_document_rejects_duplicate_tools_per_section() -> None:
    """Duplicate tool entries within a section are rejected."""
    data = minimal_policy_dict(
        allow=[
            {"tool": "search_web"},
            {"tool": "search_web"},
        ]
    )

    with pytest.raises(ValidationError, match="Duplicate tool policy entry"):
        PolicyDocument.model_validate(data)


def test_model_dump_policies_yaml_uses_camel_case() -> None:
    """model_dump_policies_yaml serializes askUser and requireApproval aliases."""
    document = PolicyDocument.model_validate(
        minimal_policy_dict(
            askUser=[{"tool": "run_shell"}],
            requireApproval=[{"tool": "delete_file"}],
        )
    )

    dumped = document.model_dump_policies_yaml()

    assert "askUser" in dumped
    assert "requireApproval" in dumped
    assert dumped["askUser"][0]["tool"] == "run_shell"
