"""Policy YAML parser and compiler."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from antigravity_agentkit.exceptions import LoadError, ValidationError
from antigravity_agentkit.schema.policies import PolicyDocument, PolicyRule

_POLICY_SECTIONS = ("allow", "deny", "askUser", "requireApproval")


def _validate_policy_keys(data: dict[str, Any]) -> None:
    """Reject unknown top-level keys and malformed section entries."""
    allowed = {"default", *_POLICY_SECTIONS}
    unknown = set(data.keys()) - allowed
    if unknown:
        raise ValidationError(f"Unknown policies.yaml keys: {sorted(unknown)}")

    for section in _POLICY_SECTIONS:
        entries = data.get(section)
        if entries is None:
            continue
        if not isinstance(entries, list):
            raise ValidationError(f"Policy section '{section}' must be a list")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValidationError(f"Policy section '{section}' entry {index} must be a mapping")
            if "tool" not in entry:
                raise ValidationError(
                    f"Policy section '{section}' entry {index} missing required 'tool'"
                )


def _normalize_policy_rules(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize policy rule entries to PolicyRule-compatible dicts."""
    normalized = dict(data)
    for section in _POLICY_SECTIONS:
        entries = normalized.get(section)
        if not entries:
            continue
        normalized[section] = [
            {"tool": entry["tool"], "when": entry.get("when")}
            for entry in entries
            if isinstance(entry, dict) and "tool" in entry
        ]
    return normalized


def parse_policies_dict(data: dict[str, Any]) -> PolicyDocument:
    """Parse policies.yaml content from a dictionary."""
    _validate_policy_keys(data)
    normalized = _normalize_policy_rules(data)
    try:
        return PolicyDocument.from_dict(normalized)
    except Exception as exc:
        raise ValidationError(f"Invalid policies configuration: {exc}") from exc


def parse_policies_yaml(path: Path) -> PolicyDocument:
    """Parse policies.yaml from disk."""
    if not path.is_file():
        raise LoadError(f"Policies file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LoadError(f"Invalid YAML in {path}: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise LoadError(f"Policies file must be a YAML mapping: {path}")
    return parse_policies_dict(raw)


def _compile_rule(rule: PolicyRule, decision: str) -> dict[str, Any]:
    result: dict[str, Any] = {"tool": rule.tool, "decision": decision}
    if rule.when is not None:
        if isinstance(rule.when, dict):
            result["when"] = dict(rule.when)
        else:
            result["when"] = rule.when.model_dump(by_alias=True, exclude_none=True)
    return result


def compile_policy_dicts(policies: PolicyDocument) -> list[dict[str, Any]]:
    """Compile policies to Antigravity-compatible policy hook dictionaries."""
    compiled: list[dict[str, Any]] = []

    for rule in policies.deny:
        compiled.append(_compile_rule(rule, "deny"))
    for rule in policies.allow:
        compiled.append(_compile_rule(rule, "allow"))
    for rule in policies.ask_user:
        compiled.append(_compile_rule(rule, "ask_user"))
    for rule in policies.require_approval:
        compiled.append(_compile_rule(rule, "require_approval"))

    if policies.default == "deny":
        compiled.append({"tool": "*", "decision": "deny", "default": True})

    return compiled


def resolve_tool_decision(
    tool_name: str,
    policies: PolicyDocument,
) -> str:
    """Resolve the effective policy decision for a tool under default-deny."""
    for rule in policies.deny:
        if rule.tool == tool_name:
            return "deny"
    for rule in policies.require_approval:
        if rule.tool == tool_name:
            return "require_approval"
    for rule in policies.ask_user:
        if rule.tool == tool_name:
            return "ask_user"
    for rule in policies.allow:
        if rule.tool == tool_name:
            return "allow"
    return policies.default


def validate_policies_yaml(path: Path) -> PolicyDocument:
    """Parse and validate policies.yaml."""
    return parse_policies_yaml(path)
