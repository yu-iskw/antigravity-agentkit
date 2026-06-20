"""Deployment manifest schemas for deployment.yaml."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_API_VERSION = "antigravity-agentkit.dev/v1alpha1"
_AGENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")

DeployTarget = Literal[
    "agent-platform",
    "agent-platform-runtime",
    "gemini-api",
    "managed-agents-api",
    "ai-studio",
    "cloud-run",
]


class DeploymentMetadata(BaseModel):
    """Identity metadata for a deployment manifest."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=64)
    namespace: str | None = Field(
        default=None,
        description="Optional non-default namespace for platform deployment metadata.",
    )

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


CaptureMessageContent = Literal["false", "event_only", "full"]
IdentityMode = Literal["agent-identity", "service-account", "oauth"]


class IdentityConfig(BaseModel):
    """Runtime identity configuration for Agent Platform."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: IdentityMode = "agent-identity"
    service_account: str | None = Field(default=None, alias="serviceAccount")

    @model_validator(mode="after")
    def validate_service_account_for_mode(self) -> IdentityConfig:
        """Require serviceAccount when mode is service-account."""
        if self.mode == "service-account" and not self.service_account:
            msg = "identity.serviceAccount is required when identity.mode is service-account."
            raise ValueError(msg)
        return self


class ObservabilityConfig(BaseModel):
    """Observability and telemetry configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    cloud_trace: bool = Field(default=True, alias="cloudTrace")
    capture_message_content: CaptureMessageContent = Field(
        default="event_only",
        alias="captureMessageContent",
    )
    big_query_analytics: bool = Field(default=False, alias="bigQueryAnalytics")
    logs_bucket: str | None = Field(default=None, alias="logsBucket")
    bq_dataset: str | None = Field(default=None, alias="bqDataset")


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
    identity: IdentityConfig | None = None
    observability: ObservabilityConfig | None = None

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
    "CaptureMessageContent",
    "DeployTarget",
    "DeploymentManifest",
    "DeploymentMetadata",
    "DeploymentSpec",
    "GatewayConfig",
    "IdentityConfig",
    "IdentityMode",
    "ObservabilityConfig",
    "ResourceLimits",
]
