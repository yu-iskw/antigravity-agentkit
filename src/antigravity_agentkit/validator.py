"""Project validation with diagnostics and policy profiles."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import yaml

from antigravity_agentkit.diagnostics import DiagnosticCollector
from antigravity_agentkit.exceptions import LoadError, ValidationError
from antigravity_agentkit.loader import (
    DEPLOYMENT_FILENAME,
    load_agent_yaml,
    load_deployment,
    load_system_md,
)
from antigravity_agentkit.mcp import assert_mcp_security, parse_mcp_dict, validate_mcp_security
from antigravity_agentkit.policies import parse_policies_dict, validate_policies_yaml
from antigravity_agentkit.schema.agent import AgentProjectData
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.skills import validate_skills
from antigravity_agentkit.subagents import load_subagents_from_specs

ValidationLevel = Literal["syntax", "schema", "security", "cloud", "full"]
ValidationProfile = Literal[
    "dev-open",
    "dev-restricted",
    "prod-readonly",
    "prod-human-approval",
    "prod-locked",
]

_LEVEL_ORDER: dict[str, int] = {
    "syntax": 1,
    "schema": 2,
    "security": 3,
    "cloud": 4,
    "full": 5,
}

_DANGEROUS_TOOLS = ("run_command", "write_file", "delete_file")
_PRODUCTION_PROFILES = frozenset({"prod-readonly", "prod-human-approval", "prod-locked"})
_PROFILES_REQUIRING_POLICIES = _PRODUCTION_PROFILES
_PROFILES_REQUIRING_SERVICE_ACCOUNT = _PRODUCTION_PROFILES


def _level_includes(requested: ValidationLevel, minimum: ValidationLevel) -> bool:
    return _LEVEL_ORDER[requested] >= _LEVEL_ORDER[minimum]


def _catch_load_errors(collector: DiagnosticCollector, callback: Callable[[], None]) -> None:
    try:
        callback()
    except LoadError as exc:
        collector.add_error("AGK-LOAD-001", str(exc))
    except ValidationError as exc:
        collector.add_error("AGK-SCHEMA-001", str(exc))
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        collector.add_error("AGK-VALID-001", str(exc))


def _validate_syntax(root: Path, data: AgentProjectData, collector: DiagnosticCollector) -> None:
    manifest_path = root / "agent.yaml"

    def load_manifest() -> None:
        load_agent_yaml(manifest_path)

    _catch_load_errors(collector, load_manifest)
    if collector.has_errors():
        return

    manifest = data.manifest
    system_path = root / manifest.spec.instructions.system

    def load_system() -> None:
        load_system_md(system_path)

    _catch_load_errors(collector, load_system)

    if manifest.spec.mcp:
        mcp_path = root / manifest.spec.mcp.file
        if mcp_path.is_file():
            try:
                json.loads(mcp_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                collector.add_error(
                    "AGK-MCP-001",
                    f"Invalid JSON in {mcp_path}: {exc}",
                    file=str(mcp_path),
                )

    if manifest.spec.policies:
        policies_path = root / manifest.spec.policies.file
        if policies_path.is_file():
            try:
                yaml.safe_load(policies_path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                collector.add_error(
                    "AGK-POLICY-001",
                    f"Invalid YAML in {policies_path}: {exc}",
                    file=str(policies_path),
                )


def _validate_schema(root: Path, data: AgentProjectData, collector: DiagnosticCollector) -> None:
    manifest = data.manifest

    def validate_skills_refs() -> None:
        if manifest.spec.skills and manifest.spec.skills.local:
            validate_skills(root, manifest.spec.skills.local)

    _catch_load_errors(collector, validate_skills_refs)

    def validate_subagents() -> None:
        if manifest.spec.subagents:
            for spec in manifest.spec.subagents:
                if spec.type == "remote":
                    raise ValidationError(
                        f"Remote subagent {spec.name!r} is not supported in v1alpha1"
                    )
            load_subagents_from_specs(root, manifest.spec.subagents)

    _catch_load_errors(collector, validate_subagents)

    if manifest.spec.skills and manifest.spec.skills.registry:
        collector.add_error(
            "AGK-SKILL-003",
            "Registry-backed skills are not supported in v1alpha1",
            file="agent.yaml",
            path="$.spec.skills.registry",
        )

    if manifest.spec.policies:
        policies_path = root / manifest.spec.policies.file
        if policies_path.is_file():
            try:
                validate_policies_yaml(policies_path)
            except (LoadError, ValidationError) as exc:
                collector.add_error(
                    "AGK-POLICY-002",
                    str(exc),
                    file=str(policies_path),
                )

    if manifest.spec.mcp and data.mcp_config is not None:
        try:
            parse_mcp_dict(data.mcp_config)
        except ValidationError as exc:
            collector.add_error("AGK-MCP-002", str(exc), file=manifest.spec.mcp.file)


def _check_prod_policies(
    root: Path, data: AgentProjectData, collector: DiagnosticCollector
) -> None:
    manifest = data.manifest
    policies_path = root / manifest.spec.policies.file if manifest.spec.policies else None
    if not data.policies:
        collector.add_error(
            "AGK-POLICY-003",
            "Production profile requires policies.yaml",
            file=str(policies_path) if policies_path else None,
        )
        return

    doc = parse_policies_dict(data.policies)
    denied_tools = {rule.tool for rule in doc.deny}
    for tool in _DANGEROUS_TOOLS:
        if tool not in denied_tools:
            collector.add_warn(
                "AGK-POLICY-007",
                f"Production agent has no explicit deny rule for {tool}",
                file=str(policies_path),
            )


def _validate_security(
    root: Path,
    data: AgentProjectData,
    collector: DiagnosticCollector,
    profile: ValidationProfile,
) -> None:
    manifest = data.manifest
    production = profile != "dev-open"

    parsed_mcp = parse_mcp_dict(data.mcp_config) if data.mcp_config else None

    if data.mcp_config and parsed_mcp is not None:
        mcp_errors = validate_mcp_security(data.mcp_config, production=production)
        for message in mcp_errors:
            code = "AGK-MCP-003"
            mcp_file = manifest.spec.mcp.file if manifest.spec.mcp else None
            if production:
                collector.add_error(code, message, file=mcp_file)
            else:
                collector.add_warn(code, message, file=mcp_file)

        if production:
            try:
                assert_mcp_security(parsed_mcp, production=True)
            except ValidationError as exc:
                collector.add_error("AGK-MCP-004", str(exc))

    if manifest.spec.mcp and parsed_mcp is not None:
        admission = manifest.spec.mcp.admission_policy
        if production and admission and admission.allowed_servers:
            configured = set(parsed_mcp.mcp_servers)
            disallowed = configured - set(admission.allowed_servers)
            if disallowed:
                collector.add_error(
                    "AGK-MCP-005",
                    "MCP servers not in admission policy: " + ", ".join(sorted(disallowed)),
                )

    if profile in _PROFILES_REQUIRING_POLICIES:
        _check_prod_policies(root, data, collector)


def _validate_cloud_agent(
    data: AgentProjectData,
    collector: DiagnosticCollector,
) -> None:
    """Validate agent-side cloud settings (runtime vertex)."""
    manifest = data.manifest
    vertex = manifest.spec.runtime.vertex

    if vertex.enabled and not vertex.project:
        collector.add_error(
            "AGK-CLOUD-001",
            "runtime.vertex.project is required when vertex.enabled is true",
            file="agent.yaml",
            path="$.spec.runtime.vertex.project",
        )


def _validate_cloud_deployment(
    data: AgentProjectData,
    deployment: DeploymentManifest,
    collector: DiagnosticCollector,
    profile: ValidationProfile,
) -> None:
    """Validate deployment.yaml cloud settings when present."""
    if deployment.metadata.name != data.manifest.metadata.name:
        collector.add_error(
            "AGK-DEPLOY-001",
            "deployment.metadata.name must match agent metadata.name",
            file="deployment.yaml",
            path="$.metadata.name",
        )

    deploy_spec = deployment.spec
    if profile in _PROFILES_REQUIRING_SERVICE_ACCOUNT and not deploy_spec.service_account:
        collector.add_error(
            "AGK-CLOUD-002",
            f"Profile {profile!r} requires deployment.serviceAccount",
            file="deployment.yaml",
            path="$.spec.serviceAccount",
        )

    if (
        deploy_spec.gateway
        and deploy_spec.gateway.enabled
        and not deploy_spec.gateway.required_endpoints
    ):
        collector.add_warn(
            "AGK-CLOUD-003",
            "Agent Gateway enabled without requiredEndpoints",
            file="deployment.yaml",
        )


def validate_deployment(
    data: AgentProjectData,
    deployment: DeploymentManifest,
    *,
    profile: ValidationProfile = "dev-open",
) -> DiagnosticCollector:
    """Validate deployment manifest against agent project data."""
    collector = DiagnosticCollector()
    _validate_cloud_deployment(data, deployment, collector, profile)
    return collector


def _validate_cloud(
    root: Path,
    data: AgentProjectData,
    collector: DiagnosticCollector,
    profile: ValidationProfile,
) -> None:
    _validate_cloud_agent(data, collector)
    deployment_path = root / DEPLOYMENT_FILENAME
    if deployment_path.is_file():
        try:
            loaded = load_deployment(root)
        except LoadError as exc:
            collector.add_error("AGK-DEPLOY-002", str(exc), file=DEPLOYMENT_FILENAME)
            return
        _validate_cloud_deployment(data, loaded, collector, profile)
    elif profile in _PROFILES_REQUIRING_SERVICE_ACCOUNT:
        collector.add_error(
            "AGK-DEPLOY-003",
            f"Profile {profile!r} requires {DEPLOYMENT_FILENAME}",
            file=DEPLOYMENT_FILENAME,
        )


def validate_project_data(
    root: Path,
    data: AgentProjectData,
    *,
    level: ValidationLevel = "schema",
    profile: ValidationProfile = "dev-open",
) -> DiagnosticCollector:
    """Validate loaded project data and return collected diagnostics."""
    collector = DiagnosticCollector()

    if _level_includes(level, "syntax"):
        _validate_syntax(root, data, collector)
        if collector.has_errors():
            return collector

    if _level_includes(level, "schema"):
        _validate_schema(root, data, collector)

    if _level_includes(level, "security"):
        _validate_security(root, data, collector, profile)

    if _level_includes(level, "cloud") or level == "full":
        _validate_cloud(root, data, collector, profile)

    return collector


def validate_project(
    root: Path,
    data: AgentProjectData,
    *,
    level: ValidationLevel = "schema",
    profile: ValidationProfile = "dev-open",
) -> DiagnosticCollector:
    """Validate loaded project data and return collected diagnostics."""
    return validate_project_data(root, data, level=level, profile=profile)


def assert_valid_project_data(
    root: Path,
    data: AgentProjectData,
    *,
    level: ValidationLevel = "schema",
    profile: ValidationProfile = "dev-open",
) -> None:
    """Raise ValidationError when validation diagnostics include errors."""
    collector = validate_project_data(root, data, level=level, profile=profile)
    if collector.has_errors():
        raise ValidationError(collector.format_all())


def assert_valid_project(
    root: Path,
    data: AgentProjectData,
    *,
    level: ValidationLevel = "schema",
    profile: ValidationProfile = "dev-open",
) -> None:
    """Backward-compatible alias for assert_valid_project_data."""
    assert_valid_project_data(root, data, level=level, profile=profile)
