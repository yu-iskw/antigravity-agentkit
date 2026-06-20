"""Tests for eval suite schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from antigravity_agentkit.schema.evals import EvalCase, EvalSuite
from antigravity_agentkit.tests.schema.conftest import minimal_eval_dict


def test_eval_case_rejects_blank_name() -> None:
    """Eval case names must not be blank."""
    with pytest.raises(ValidationError, match="blank"):
        EvalCase.model_validate({"name": "   ", "input": "hello"})


def test_eval_suite_rejects_duplicate_case_names() -> None:
    """Duplicate case names within a suite are rejected."""
    data = minimal_eval_dict(
        cases=[
            {"name": "smoke", "input": "hello"},
            {"name": "smoke", "input": "again"},
        ]
    )

    with pytest.raises(ValidationError, match="Duplicate eval case name"):
        EvalSuite.model_validate(data)


def test_eval_suite_rejects_execution_mode() -> None:
    """Checked-in suites cannot select live or paid execution modes."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvalSuite.model_validate(minimal_eval_dict(mode="live"))


def test_eval_suite_from_dict_validates() -> None:
    """EvalSuite.from_dict accepts valid data and rejects invalid suites."""
    suite = EvalSuite.from_dict(minimal_eval_dict())

    assert suite.version == 1
    assert len(suite.cases) == 1
    assert suite.cases[0].name == "smoke"

    with pytest.raises(ValidationError):
        EvalSuite.from_dict(minimal_eval_dict(cases=[]))
