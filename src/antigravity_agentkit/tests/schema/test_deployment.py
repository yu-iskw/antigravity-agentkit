"""Tests for deployment.yaml schema models."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.tests.schema.conftest import minimal_deployment_dict


@pytest.mark.parametrize(
    "bad_name",
    [
        "Ship-Agent",
        "ship_agent",
        "1ship",
        "-ship",
        "",
        "a" * 65,
    ],
)
def test_deployment_metadata_rejects_bad_names(bad_name: str) -> None:
    """Deployment names must be lowercase hyphenated identifiers."""
    data = minimal_deployment_dict(metadata={"name": bad_name})

    with pytest.raises(ValidationError):
        DeploymentManifest.model_validate(data)


def test_deployment_spec_rejects_max_less_than_min() -> None:
    """maxInstances must be greater than or equal to minInstances."""
    data = minimal_deployment_dict(
        spec={
            "target": "agent-platform",
            "minInstances": 2,
            "maxInstances": 1,
        }
    )

    with pytest.raises(ValidationError, match="maxInstances"):
        DeploymentManifest.model_validate(data)


def test_deployment_spec_allows_equal_bounds() -> None:
    """Equal min and max instance bounds are valid."""
    manifest = DeploymentManifest.model_validate(
        minimal_deployment_dict(
            spec={
                "target": "agent-platform",
                "minInstances": 1,
                "maxInstances": 1,
            }
        )
    )

    assert manifest.spec.min_instances == 1
    assert manifest.spec.max_instances == 1


def test_deployment_manifest_from_ship_fixture(ship_agent_dir: Path) -> None:
    """ship_agent deployment.yaml validates as DeploymentManifest."""
    raw = yaml.safe_load((ship_agent_dir / "deployment.yaml").read_text(encoding="utf-8"))
    manifest = DeploymentManifest.model_validate(raw)

    assert manifest.metadata.name == "ship-agent"
    assert manifest.spec.target == "agent-platform"
    assert manifest.spec.gateway is not None
    assert manifest.spec.gateway.enabled is True
