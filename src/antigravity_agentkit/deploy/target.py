"""Deploy target protocol and context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from antigravity_agentkit.deploy.capabilities import TargetCapabilities
from antigravity_agentkit.ir import CompiledAgentIR
from antigravity_agentkit.json_types import JsonValue
from antigravity_agentkit.schema.deployment import DeploymentManifest


@dataclass(frozen=True)
class DeployContext:
    """Runtime context for deploy target handlers."""

    project_id: str
    location: str
    output_path: Path | None = None
    dry_run: bool | None = None


class DeployTarget(Protocol):
    """Protocol implemented by deploy target adapters."""

    name: str
    aliases: tuple[str, ...]
    capabilities: TargetCapabilities

    def validate_ir(
        self,
        ir: CompiledAgentIR,
        deployment: DeploymentManifest,
        context: DeployContext,
    ) -> None: ...

    def build_config(
        self,
        ir: CompiledAgentIR,
        deployment: DeploymentManifest,
        context: DeployContext,
    ) -> dict[str, JsonValue]: ...

    def deploy(
        self,
        ir: CompiledAgentIR,
        deployment: DeploymentManifest,
        context: DeployContext,
        *,
        project_root: Path,
    ) -> dict[str, JsonValue]: ...
