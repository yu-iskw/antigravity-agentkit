"""Tool and MCP policy document schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolicyWhen(BaseModel):
    """Conditional clause for ask-user or approval policies."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    risk: Literal["low", "medium", "high"] | None = None
    estimated_bytes_processed_gt: int | None = Field(
        default=None,
        alias="estimatedBytesProcessedGt",
        ge=0,
    )


class PolicyRule(BaseModel):
    """A single tool policy rule."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tool: str = Field(..., min_length=1)
    when: PolicyWhen | dict[str, Any] | None = None

    @field_validator("tool")
    @classmethod
    def validate_tool_not_blank(cls, value: str) -> str:
        """Reject blank tool identifiers."""
        stripped = value.strip()
        if not stripped:
            msg = "Policy tool name must not be blank."
            raise ValueError(msg)
        return stripped


class PolicyDocument(BaseModel):
    """Tool, MCP, and risk policies from policies.yaml."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    default: Literal["allow", "deny"] = "deny"
    allow: list[PolicyRule] = Field(default_factory=list)
    deny: list[PolicyRule] = Field(default_factory=list)
    ask_user: list[PolicyRule] = Field(default_factory=list, alias="askUser")
    require_approval: list[PolicyRule] = Field(
        default_factory=list,
        alias="requireApproval",
    )

    @field_validator("allow", "deny", "ask_user", "require_approval")
    @classmethod
    def validate_unique_tools_per_section(
        cls,
        value: list[PolicyRule],
    ) -> list[PolicyRule]:
        """Reject duplicate tool entries within a policy section."""
        seen: set[str] = set()
        for rule in value:
            if rule.tool in seen:
                msg = f"Duplicate tool policy entry: {rule.tool!r}."
                raise ValueError(msg)
            seen.add(rule.tool)
        return value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyDocument:
        """Build from a raw policies.yaml dictionary."""
        return cls.model_validate(data)

    def model_dump_policies_yaml(self) -> dict[str, Any]:
        """Serialize to policies.yaml-compatible dict with camelCase aliases."""
        return self.model_dump(by_alias=True, exclude_none=True)


# Backward-compatible alias used by compiler modules.
PoliciesDocument = PolicyDocument
