"""Agent manifest schemas for agent.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_API_VERSION = "antigravity-agentkit.dev/v1alpha1"
_AGENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


class AgentMetadata(BaseModel):
    """Identity and catalog metadata for an agent."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=64)
    display_name: str | None = Field(default=None, alias="displayName")
    description: str | None = None
    owner: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name_convention(cls, value: str) -> str:
        """Enforce lowercase hyphenated agent names."""
        stripped = value.strip()
        if not _AGENT_NAME_PATTERN.match(stripped):
            msg = (
                "Agent name must start with a lowercase letter and contain only "
                "lowercase letters, digits, and hyphens."
            )
            raise ValueError(msg)
        return stripped


class VertexConfig(BaseModel):
    """Vertex AI / Gemini Enterprise runtime configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    project: str | None = None
    location: str | None = None

    @model_validator(mode="after")
    def validate_project_when_enabled(self) -> VertexConfig:
        """Require project when Vertex is enabled."""
        if self.enabled and not self.project:
            msg = "runtime.vertex.project is required when vertex.enabled is true."
            raise ValueError(msg)
        return self


class CapabilitiesConfig(BaseModel):
    """Agent capability restrictions."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["open", "restricted", "locked"] = "restricted"


class RuntimeSpec(BaseModel):
    """Runtime framework and model configuration."""

    model_config = ConfigDict(extra="forbid")

    framework: Literal["antigravity"] = "antigravity"
    model: str | None = None
    vertex: VertexConfig = Field(default_factory=VertexConfig)
    capabilities: CapabilitiesConfig = Field(default_factory=CapabilitiesConfig)


class InstructionsSpec(BaseModel):
    """Instruction file references."""

    model_config = ConfigDict(extra="forbid")

    system: str = Field(..., min_length=1)


class McpAdmissionPolicy(BaseModel):
    """Production MCP server admission allowlist."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    allowed_servers: list[str] = Field(default_factory=list, alias="allowedServers")


class McpSpec(BaseModel):
    """MCP configuration reference within agent.yaml."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    file: str = Field(default="mcp.json", min_length=1)
    admission_policy: McpAdmissionPolicy | None = Field(
        default=None,
        alias="admissionPolicy",
    )


class RegistrySkillRef(BaseModel):
    """Reference to a skill published in Skill Registry."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    revision: str = "default"
    mode: Literal["pinned", "floating"] = "pinned"


class SkillsSpec(BaseModel):
    """Local and registry-backed skill references."""

    model_config = ConfigDict(extra="forbid")

    local: list[str] = Field(default_factory=list)
    registry: list[RegistrySkillRef] = Field(default_factory=list)


class SubagentAuth(BaseModel):
    """Authentication mode for remote subagents."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["agent-identity", "service-account", "oauth"] = "agent-identity"


class SubagentSpec(BaseModel):
    """Local markdown or remote registry-backed subagent."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(..., min_length=1)
    type: Literal["markdown", "remote"] = "markdown"
    file: str | None = None
    tools: list[str] = Field(default_factory=list)
    registry_ref: str | None = Field(default=None, alias="registryRef")
    auth: SubagentAuth | None = None

    @model_validator(mode="after")
    def validate_subagent_shape(self) -> SubagentSpec:
        """Enforce required fields per subagent type."""
        if self.type == "markdown" and not self.file:
            msg = "Markdown subagents require spec.subagents[].file."
            raise ValueError(msg)
        if self.type == "remote" and not self.registry_ref:
            msg = "Remote subagents require spec.subagents[].registryRef."
            raise ValueError(msg)
        return self


class PoliciesSpec(BaseModel):
    """Policy file reference within agent.yaml."""

    model_config = ConfigDict(extra="forbid")

    file: str = Field(default="policies.yaml", min_length=1)


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
    """Agent Runtime deployment configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    target: Literal["agent-runtime", "local"] = "agent-runtime"
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


class AgentRegistryConfig(BaseModel):
    """Agent Registry publishing options."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    enabled: bool = False


class SkillRegistryConfig(BaseModel):
    """Skill Registry publishing options."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    publish_local_skills: bool = Field(default=False, alias="publishLocalSkills")


class McpRegistryConfig(BaseModel):
    """MCP server registration options."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    register_servers: bool = Field(default=False, alias="register")


class RegistrySpec(BaseModel):
    """Registry integration configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    agent_registry: AgentRegistryConfig | None = Field(
        default=None,
        alias="agentRegistry",
    )
    skill_registry: SkillRegistryConfig | None = Field(
        default=None,
        alias="skillRegistry",
    )
    mcp_servers: McpRegistryConfig | None = Field(default=None, alias="mcpServers")


class EvalsSpec(BaseModel):
    """Evaluation file references within agent.yaml."""

    model_config = ConfigDict(extra="forbid")

    files: list[str] = Field(default_factory=list)


class AgentSpec(BaseModel):
    """Agent behavioral, governance, and deployment specification."""

    model_config = ConfigDict(extra="forbid")

    runtime: RuntimeSpec = Field(default_factory=RuntimeSpec)
    instructions: InstructionsSpec
    mcp: McpSpec | None = None
    skills: SkillsSpec | None = None
    subagents: list[SubagentSpec] = Field(default_factory=list)
    policies: PoliciesSpec | None = None
    deployment: DeploymentSpec | None = None
    registry: RegistrySpec | None = None
    evals: EvalsSpec | None = None

    @field_validator("subagents")
    @classmethod
    def validate_unique_subagent_names(
        cls,
        value: list[SubagentSpec],
    ) -> list[SubagentSpec]:
        """Reject duplicate subagent names."""
        seen: set[str] = set()
        for subagent in value:
            if subagent.name in seen:
                msg = f"Duplicate subagent name: {subagent.name!r}."
                raise ValueError(msg)
            seen.add(subagent.name)
        return value


class AgentManifest(BaseModel):
    """Top-level agent.yaml manifest."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    api_version: Literal["antigravity-agentkit.dev/v1alpha1"] = Field(
        default=_API_VERSION,
        alias="apiVersion",
    )
    kind: Literal["Agent"] = "Agent"
    metadata: AgentMetadata
    spec: AgentSpec

    def model_dump_agent_yaml(self) -> dict[str, Any]:
        """Serialize to agent.yaml-compatible dict with camelCase aliases."""
        return self.model_dump(by_alias=True, exclude_none=True)


@dataclass
class AgentProjectData:
    """Raw loaded contents of an agent directory."""

    root: Path
    manifest: AgentManifest
    manifest_raw: dict[str, Any]
    system_instructions: str
    mcp_config: dict[str, Any] | None = None
    mcp_raw: str | None = None
    policies: dict[str, Any] | None = None
    policies_raw: str | None = None
    skills: dict[str, Any] = field(default_factory=dict)
    subagents: dict[str, Any] = field(default_factory=dict)
    evals: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CompiledAgentConfig:
    """Compiled Antigravity runtime configuration."""

    system_instructions: str
    mcp_servers: list[dict[str, Any]] = field(default_factory=list)
    tools: list[Any] = field(default_factory=list)
    runtime_tools: list[Any] = field(default_factory=list)
    policies: list[dict[str, Any]] = field(default_factory=list)
    vertex: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    skill_index: Any = None


# Re-export related document types commonly loaded alongside manifests.
__all__ = [
    "AgentManifest",
    "AgentMetadata",
    "AgentProjectData",
    "AgentRegistryConfig",
    "AgentSpec",
    "CapabilitiesConfig",
    "CompiledAgentConfig",
    "DeploymentSpec",
    "EvalsSpec",
    "GatewayConfig",
    "InstructionsSpec",
    "McpAdmissionPolicy",
    "McpRegistryConfig",
    "McpSpec",
    "PoliciesSpec",
    "RegistrySkillRef",
    "RegistrySpec",
    "ResourceLimits",
    "RuntimeSpec",
    "SkillRegistryConfig",
    "SkillsSpec",
    "SubagentAuth",
    "SubagentSpec",
    "VertexConfig",
]
