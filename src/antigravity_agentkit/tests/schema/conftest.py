"""Shared dict builders for schema unit tests."""

from __future__ import annotations


def minimal_manifest_dict(**overrides: object) -> dict:
    """Build a minimal valid agent manifest dict with optional overrides."""
    base = {
        "apiVersion": "antigravity-agentkit.dev/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "name": "test-agent",
            "displayName": "Test Agent",
        },
        "spec": {
            "instructions": {"system": "SYSTEM.md"},
        },
    }
    for key, value in overrides.items():
        if key == "metadata" and isinstance(value, dict):
            base["metadata"].update(value)
        elif key == "spec" and isinstance(value, dict):
            base["spec"].update(value)
        else:
            base[key] = value
    return base


def minimal_deployment_dict(**overrides: object) -> dict:
    """Build a minimal valid deployment manifest dict with optional overrides."""
    base = {
        "apiVersion": "antigravity-agentkit.dev/v1alpha1",
        "kind": "Deployment",
        "metadata": {"name": "test-deployment"},
        "spec": {"target": "agent-platform"},
    }
    for key, value in overrides.items():
        if key == "metadata" and isinstance(value, dict):
            base["metadata"].update(value)
        elif key == "spec" and isinstance(value, dict):
            base["spec"].update(value)
        else:
            base[key] = value
    return base


def minimal_policy_dict(**overrides: object) -> dict:
    """Build a minimal valid policy document dict with optional overrides."""
    base: dict = {"default": "deny"}
    base.update(overrides)
    return base


def minimal_eval_dict(**overrides: object) -> dict:
    """Build a minimal valid eval suite dict with optional overrides."""
    base = {
        "version": 1,
        "cases": [
            {
                "name": "smoke",
                "input": "hello",
            }
        ],
    }
    base.update(overrides)
    return base


def minimal_mcp_dict(**overrides: object) -> dict:
    """Build a minimal valid MCP config dict with optional overrides."""
    base: dict[str, object] = {
        "mcpServers": {
            "clock": {"command": "python3"},
        }
    }
    base.update(overrides)
    return base
