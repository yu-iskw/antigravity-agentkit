"""Tests for platform module pure helpers."""

from __future__ import annotations

from pathlib import Path

from antigravity_agentkit.platform.agent_engines import (
    build_agent_engine_api_config,
    merge_platform_deploy_fields,
    package_digest,
)
from antigravity_agentkit.platform.deploy_state import (
    record_deploy,
    resolve_rollback_target,
)
from antigravity_agentkit.platform.evals import compare_eval_results, export_platform_dataset
from antigravity_agentkit.platform.iam import identity_api_fields, resolve_identity
from antigravity_agentkit.platform.observability import observability_env_vars
from antigravity_agentkit.platform.runtime_adapter import PLATFORM_ENTRYPOINT_MODULE
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest


def test_identity_api_fields_service_account() -> None:
    """Identity block maps to Platform identity_type and service account."""
    deployment = DeploymentManifest.model_validate(
        {
            "apiVersion": "antigravity-agentkit.dev/v1alpha1",
            "kind": "Deployment",
            "metadata": {"name": "demo"},
            "spec": {
                "target": "agent-platform",
                "identity": {
                    "mode": "service-account",
                    "serviceAccount": "demo@project.iam.gserviceaccount.com",
                },
            },
        }
    )
    fields = identity_api_fields(deployment)
    assert fields["identity_type"] == "SERVICE_ACCOUNT"
    assert fields["service_account"] == "demo@project.iam.gserviceaccount.com"


def test_resolve_identity_legacy_service_account() -> None:
    """Legacy spec.serviceAccount maps to service-account mode."""
    deployment = DeploymentManifest.model_validate(
        {
            "apiVersion": "antigravity-agentkit.dev/v1alpha1",
            "kind": "Deployment",
            "metadata": {"name": "demo"},
            "spec": {
                "target": "agent-platform",
                "serviceAccount": "legacy@project.iam.gserviceaccount.com",
            },
        }
    )
    identity = resolve_identity(deployment)
    assert identity.mode == "service-account"
    assert identity.service_account == "legacy@project.iam.gserviceaccount.com"


def test_observability_env_vars() -> None:
    """Observability block compiles OTEL environment variables."""
    deployment = DeploymentManifest.model_validate(
        {
            "apiVersion": "antigravity-agentkit.dev/v1alpha1",
            "kind": "Deployment",
            "metadata": {"name": "demo"},
            "spec": {
                "target": "agent-platform",
                "observability": {
                    "cloudTrace": True,
                    "captureMessageContent": "event_only",
                    "logsBucket": "gs://demo-logs",
                },
            },
        }
    )
    env = observability_env_vars(deployment)
    assert env["OTEL_SEMCONV_STABILITY_OPT_IN"] == "gen_ai_latest_experimental"
    assert env["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] == "EVENT_ONLY"
    assert env["LOGS_BUCKET_NAME"] == "gs://demo-logs"


def test_merge_platform_deploy_fields() -> None:
    """Platform deploy fields include adapter entrypoint and class methods."""
    merged = merge_platform_deploy_fields(
        {"display_name": "Demo"},
        env_vars={"LOGS_BUCKET_NAME": "gs://x"},
        identity_fields={"identity_type": "AGENT_IDENTITY"},
    )
    assert merged["entrypoint_module"] == PLATFORM_ENTRYPOINT_MODULE
    assert merged["agent_framework"] == "custom"
    assert merged["class_methods"]
    assert merged["env_vars"]["LOGS_BUCKET_NAME"] == "gs://x"


def test_build_agent_engine_api_config(tmp_path: Path) -> None:
    """API config uses package directory as source_packages."""
    package_dir = tmp_path / "pkg"
    package_dir.mkdir()
    (package_dir / "agent.py").write_text("root_agent = object()\n", encoding="utf-8")
    (package_dir / "requirements.txt").write_text(
        "antigravity-agentkit[antigravity]\n", encoding="utf-8"
    )

    api_config = build_agent_engine_api_config(
        {
            "display_name": "Demo",
            "entrypoint_module": "platform_adapter",
            "entrypoint_object": "platform_app",
            "class_methods": [{"name": "query", "api_mode": "", "parameters": {}}],
        },
        package_dir,
    )
    assert api_config["source_packages"] == [str(package_dir)]
    assert api_config["display_name"] == "Demo"


def test_package_digest_is_stable(tmp_path: Path) -> None:
    """Package digest is deterministic for the same files."""
    package_dir = tmp_path / "pkg"
    package_dir.mkdir()
    (package_dir / "agent.py").write_text("x\n", encoding="utf-8")
    first = package_digest(package_dir)
    second = package_digest(package_dir)
    assert first == second
    assert first.startswith("sha256:")


def test_record_deploy_and_rollback_target(tmp_path: Path) -> None:
    """Deploy state history supports rollback resolution."""
    package_dir = tmp_path / "pkg"
    package_dir.mkdir()
    first = record_deploy(
        package_dir,
        resource_name="projects/p/locations/l/reasoningEngines/1",
        package_digest="sha256:aaa",
        git_sha="abc123",
        previous=None,
    )
    second = record_deploy(
        package_dir,
        resource_name="projects/p/locations/l/reasoningEngines/1",
        package_digest="sha256:bbb",
        git_sha="def456",
        previous=first,
    )
    target = resolve_rollback_target(second, "abc123")
    assert target.package_digest == "sha256:aaa"


def test_export_platform_dataset(hello_world_agent_dir: Path) -> None:
    """Export includes agent name even when no eval suites exist."""
    project = AgentProject.load(hello_world_agent_dir)
    exported = export_platform_dataset(project)
    assert exported["agentName"] == "hello-world"
    assert not exported["cases"]


def test_compare_eval_results(tmp_path: Path) -> None:
    """Compare detects changed eval result files."""
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text('{"score": 1}', encoding="utf-8")
    candidate.write_text('{"score": 2}', encoding="utf-8")
    summary = compare_eval_results(baseline, candidate)
    assert summary["changed"] is True
