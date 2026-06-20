"""Agent Platform Runtime deployment adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antigravity_agentkit.deploy._common import (
    merge_deployment_labels,
    resolve_display_name,
    should_dry_run,
    write_dry_run_artifact,
    write_registry_metadata_artifact,
)
from antigravity_agentkit.deploy.capabilities import (
    AGENT_PLATFORM_RUNTIME_CAPABILITIES,
    validate_ir_for_target,
)
from antigravity_agentkit.deploy.package import build_source_package
from antigravity_agentkit.deploy.target import DeployContext
from antigravity_agentkit.ir import CompiledAgentIR
from antigravity_agentkit.platform.agent_engines import (
    create_or_update_agent_engine,
    merge_platform_deploy_fields,
)
from antigravity_agentkit.platform.iam import identity_api_fields
from antigravity_agentkit.platform.observability import observability_env_vars
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest

name = "agent-platform-runtime"
aliases = ("agent-platform", "agent-platform-runtime")
capabilities = AGENT_PLATFORM_RUNTIME_CAPABILITIES


def validate_ir(
    ir: CompiledAgentIR,
    deployment: DeploymentManifest,
    context: DeployContext,
) -> None:
    """Validate IR against Agent Platform Runtime capabilities."""
    del context
    validate_ir_for_target(
        ir,
        deployment,
        capabilities,
        unsupported_hint="Remove unsupported features or choose a different target.",
    )


def build_deployment_config(  # noqa: PLR0913
    project: AgentProject,
    ir: CompiledAgentIR,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
    *,
    package_dir: Path | None = None,
) -> dict[str, Any]:
    """Build Agent Runtime deployment configuration dictionary."""
    manifest = project.manifest
    deploy_spec = deployment.spec

    display_name = resolve_display_name(
        manifest.metadata.display_name,
        manifest.metadata.name,
        deploy_spec.display_name,
    )

    config: dict[str, Any] = {
        "source_packages": [str(package_dir or project.root)],
        "requirements_file": "requirements.txt",
        "display_name": display_name,
        "description": manifest.metadata.description or "",
        "labels": merge_deployment_labels(
            manifest.metadata.labels,
            deploy_spec.labels,
            manifest.metadata.name,
        ),
        "project": project_id,
        "location": location,
        "target": name,
    }

    if ir.vertex.enabled:
        config["vertex"] = {
            "project": ir.vertex.project or project_id,
            "location": ir.vertex.location or location,
        }

    identity_fields = identity_api_fields(deployment)
    service_account = identity_fields.get("service_account") or deploy_spec.service_account
    if service_account:
        config["service_account"] = service_account
    if deploy_spec.min_instances is not None:
        config["min_instances"] = deploy_spec.min_instances
    if deploy_spec.max_instances is not None:
        config["max_instances"] = deploy_spec.max_instances
    if deploy_spec.container_concurrency is not None:
        config["container_concurrency"] = deploy_spec.container_concurrency
    if deploy_spec.resource_limits:
        limits: dict[str, str] = {}
        if deploy_spec.resource_limits.cpu:
            limits["cpu"] = deploy_spec.resource_limits.cpu
        if deploy_spec.resource_limits.memory:
            limits["memory"] = deploy_spec.resource_limits.memory
        if limits:
            config["resource_limits"] = limits
    if deploy_spec.gateway and deploy_spec.gateway.enabled:
        config["gateway"] = deploy_spec.gateway.model_dump(by_alias=True, exclude_none=True)
        config["registry"] = {
            "scope": capabilities.registry_scope,
            "metadata_file": "registry-metadata.json",
        }

    env_vars = observability_env_vars(deployment)
    return merge_platform_deploy_fields(
        config,
        env_vars=env_vars,
        identity_fields=identity_fields,
    )


def deploy(  # noqa: PLR0913
    project: AgentProject,
    deployment: DeploymentManifest,
    project_id: str,
    location: str,
    *,
    output_path: str | Path | None = None,
    dry_run: bool | None = None,
    resource_name: str | None = None,
    status_only: bool = False,
) -> dict[str, Any]:
    """Deploy agent to Agent Platform Runtime or write config in dry-run mode."""
    ir = project.compile()
    context = DeployContext(
        project_id=project_id,
        location=location,
        output_path=Path(output_path) if output_path else None,
        dry_run=dry_run,
    )
    validate_ir(ir, deployment, context)

    package_dir = project.root / ".build" / project.manifest.metadata.name
    if status_only:
        from antigravity_agentkit.platform.rollback import deploy_status_summary

        if not package_dir.is_dir():
            package_dir = build_source_package(
                project,
                compiled=ir,
                deployment=deployment,
            )
        return deploy_status_summary(
            package_dir,
            project_id=project_id,
            location=location,
            resource_name=resource_name,
        )

    package_dir = build_source_package(
        project,
        compiled=ir,
        deployment=deployment,
    )
    config = build_deployment_config(
        project,
        ir,
        deployment,
        project_id,
        location,
        package_dir=package_dir,
    )
    config["source_packages"] = [str(package_dir)]

    write_registry_metadata_artifact(
        ir,
        deployment,
        target=capabilities,
        location=location,
        path=package_dir / "registry-metadata.json",
    )

    if not should_dry_run(dry_run=dry_run):
        mcp_names = [server.name for server in ir.mcp_servers]
        return create_or_update_agent_engine(
            config,
            package_dir,
            project_id=project_id,
            location=location,
            resource_name=resource_name,
            mcp_server_names=mcp_names,
        )

    out = Path(output_path or project.root / ".build" / "deployment-config.json")
    return write_dry_run_artifact(out, config, extra={"package_dir": str(package_dir)})
