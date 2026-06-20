"""Evaluation suite schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EvalMode = Literal["mock", "live", "platform"]


class EvalJudge(BaseModel):
    """Optional LLM-as-judge configuration for an eval case."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    prompt_template: str | None = Field(default=None, alias="promptTemplate")
    judge_model: str | None = Field(default=None, alias="judgeModel")


class EvalExpected(BaseModel):
    """Expected assertions for an evaluation case."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    must_mention: list[str] = Field(default_factory=list, alias="mustMention")
    must_not_mention: list[str] = Field(default_factory=list, alias="mustNotMention")
    max_tool_calls: int | None = Field(default=None, alias="maxToolCalls", ge=0)
    max_latency_seconds: float | None = Field(
        default=None,
        alias="maxLatencySeconds",
        ge=0,
    )
    forbidden_patterns: list[str] = Field(
        default_factory=list,
        alias="forbiddenPatterns",
    )
    reference_answer: str | None = Field(default=None, alias="referenceAnswer")
    metric: str | None = None
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class EvalToolConstraints(BaseModel):
    """Tool allow/deny constraints for an evaluation case."""

    model_config = ConfigDict(extra="forbid")

    allowed: list[str] = Field(default_factory=list)
    denied: list[str] = Field(default_factory=list)


class EvalCase(BaseModel):
    """A single evaluation test case."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    input: str = Field(..., min_length=1)
    expected: EvalExpected = Field(default_factory=EvalExpected)
    tools: EvalToolConstraints = Field(default_factory=EvalToolConstraints)
    judge: EvalJudge = Field(default_factory=EvalJudge)

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, value: str) -> str:
        """Reject blank case names."""
        stripped = value.strip()
        if not stripped:
            msg = "Eval case name must not be blank."
            raise ValueError(msg)
        return stripped


class EvalSuite(BaseModel):
    """Evaluation suite from evals/*.yaml."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(..., ge=1)
    mode: EvalMode = "mock"
    cases: list[EvalCase] = Field(..., min_length=1)

    @field_validator("cases")
    @classmethod
    def validate_unique_case_names(cls, value: list[EvalCase]) -> list[EvalCase]:
        """Reject duplicate case names within a suite."""
        seen: set[str] = set()
        for case in value:
            if case.name in seen:
                msg = f"Duplicate eval case name: {case.name!r}."
                raise ValueError(msg)
            seen.add(case.name)
        return value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalSuite:
        """Build from a raw eval YAML dictionary."""
        return cls.model_validate(data)
