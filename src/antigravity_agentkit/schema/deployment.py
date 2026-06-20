"""Deployment manifest schemas for deployment.yaml."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_API_VERSION = "antigravity-agentkit.dev/v1alpha1"
_AGENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")

DeployTarget = Literal["agent-platform", "gemini-api", "ai-studio", "cloud-run"]


class DeploymentMetadata(BaseModel):
    """Identity metadata for a deployment manifest."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def validate_name_convention(cls, value: str) -> str:
        """Enforce lowercase hyphenated deployment names."""
        stripped = value.strip()
        if not _AGENT_NAME_PATTERN.match(stripped):
            msg = (
                "Deployment name must start with a lowercase letter and contain only "
                "lowercase letters, digits, and hyphens."
            )
            raise ValueError(msg)
        return stripped


class ResourceLimits(BaseModel):
    """Container resource limits for deployment."""

    model_config = ConfigDict(extra="forbid")

    cpu: str | None = None
    memory: str | None = None


class GatewayConfig(BaseModel):
    """Agent Gateway ingress/egress configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    enabled: bool = False
    egress_policy: str | None = Field(default=None, alias="egressPolicy")
    required_endpoints: list[str] = Field(
        default_factory=list,
        alias="requiredEndpoints",
    )


class DeploymentSpec(BaseModel):
    """Platform deployment configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    target: DeployTarget = "agent-platform"
    display_name: str | None = Field(default=None, alias="displayName")
    service_account: str | None = Field(default=None, alias="serviceAccount")
    min_instances: int | None = Field(default=None, alias="minInstances", ge=0)
    max_instances: int | None = Field(default=None, alias="maxInstances", ge=0)
    resource_limits: ResourceLimits | None = Field(
        default=None,
        alias="resourceLimits",
    )
    container_concurrency: int | None = Field(
        default=None,
        alias="containerConcurrency",
        ge=1,
    )
    labels: dict[str, str] = Field(default_factory=dict)
    gateway: GatewayConfig | None = None

    @model_validator(mode="after")
    def validate_instance_bounds(self) -> DeploymentSpec:
        """Ensure max_instances is not less than min_instances."""
        if (
            self.min_instances is not None
            and self.max_instances is not None
            and self.max_instances < self.min_instances
        ):
            msg = "deployment.maxInstances must be >= deployment.minInstances."
            raise ValueError(msg)
        return self


class DeploymentManifest(BaseModel):
    """Top-level deployment.yaml manifest."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    api_version: Literal["antigravity-agentkit.dev/v1alpha1"] = Field(
        default=_API_VERSION,
        alias="apiVersion",
    )
    kind: Literal["Deployment"] = "Deployment"
    metadata: DeploymentMetadata
    spec: DeploymentSpec


__all__ = [
    "DeployTarget",
    "DeploymentManifest",
    "DeploymentMetadata",
    "DeploymentSpec",
    "GatewayConfig",
    "ResourceLimits",
]
