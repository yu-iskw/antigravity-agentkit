"""Tests for platform module pure helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from antigravity_agentkit.exceptions import EvalError
from antigravity_agentkit.platform.agent_engines import (
    build_agent_engine_api_config,
    create_or_update_agent_engine,
    merge_platform_deploy_fields,
    package_digest,
)
from antigravity_agentkit.platform.deploy_state import (
    deploy_state_path,
    load_deploy_state,
    record_deploy,
    resolve_rollback_target,
)
from antigravity_agentkit.platform.evals import (
    compare_eval_results,
    export_platform_dataset,
    run_platform_eval_suite,
)
from antigravity_agentkit.platform.iam import identity_api_fields, resolve_identity
from antigravity_agentkit.platform.observability import observability_env_vars
from antigravity_agentkit.platform.rollback import rollback_agent_engine
from antigravity_agentkit.platform.runtime_adapter import PLATFORM_ENTRYPOINT_MODULE
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest

_MAX_DEPLOY_HISTORY = 10
_RETAINED_DEPLOY_REVISIONS = _MAX_DEPLOY_HISTORY + 1


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
    record_deploy(
        package_dir,
        resource_name="projects/p/locations/l/reasoningEngines/1",
        package_digest="sha256:aaa",
        git_sha="abc123",
    )
    second = record_deploy(
        package_dir,
        resource_name="projects/p/locations/l/reasoningEngines/1",
        package_digest="sha256:bbb",
        git_sha="def456",
    )
    target = resolve_rollback_target(second, "abc123")
    assert target.package_digest == "sha256:aaa"


def test_live_deploy_archives_revisions_outside_rebuilt_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated deploys retain immutable source packages and durable history."""
    package_dir = tmp_path / ".build" / "demo"
    package_dir.mkdir(parents=True)
    calls: list[dict[str, object]] = []

    class FakeClient:
        def create(self, *, config: dict[str, object]) -> dict[str, str]:
            calls.append(config)
            return {"resourceName": "projects/p/locations/l/reasoningEngines/1"}

        def update(self, *, name: str, config: dict[str, object]) -> dict[str, str]:
            assert name.endswith("/1")
            calls.append(config)
            return {"resourceName": name}

        def get(self, *, name: str) -> dict[str, str]:
            return {"resourceName": name}

    def write_package(digest: str, content: str) -> None:
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "agent.py").write_text(content, encoding="utf-8")
        (package_dir / "requirements.txt").write_text("example\n", encoding="utf-8")
        (package_dir / "agentkit.lock.json").write_text(
            f'{{"packageDigest": "sha256:{digest}"}}',
            encoding="utf-8",
        )

    monkeypatch.setenv("AGK_GIT_SHA", "current-deploy")
    write_package("a" * 64, "first\n")
    first = create_or_update_agent_engine(
        {}, package_dir, project_id="p", location="l", client=FakeClient()
    )
    first_archive = Path(first["packageDir"])
    assert first_archive.is_dir()

    for child in package_dir.iterdir():
        child.unlink()
    package_dir.rmdir()
    write_package("b" * 64, "second\n")
    create_or_update_agent_engine(
        {},
        package_dir,
        project_id="p",
        location="l",
        resource_name=first["resourceName"],
        client=FakeClient(),
    )

    state = load_deploy_state(package_dir)
    assert state is not None
    assert state.git_sha == "current-deploy"
    assert deploy_state_path(package_dir).is_file()
    assert len(state.history) == 1
    assert Path(state.history[0].package_dir) == first_archive
    assert (first_archive / "agent.py").read_text(encoding="utf-8") == "first\n"
    assert (Path(state.package_dir) / "agent.py").read_text(encoding="utf-8") == "second\n"
    assert calls[0]["source_packages"] == [str(first_archive)]


def test_deploy_revision_retention_keeps_current_plus_ten(tmp_path: Path) -> None:
    """Revision pruning retains only packages referenced by bounded history."""
    package_dir = tmp_path / ".build" / "demo"
    for index in range(12):
        revision = package_dir.parent / ".deploy" / package_dir.name / "revisions" / f"{index:064x}"
        revision.mkdir(parents=True)
        record_deploy(
            package_dir,
            resource_name="resource",
            package_digest=f"sha256:{index:064x}",
            git_sha=str(index),
            deployed_package_dir=revision,
        )

    state = load_deploy_state(package_dir)
    assert state is not None
    assert len(state.history) == _MAX_DEPLOY_HISTORY
    revisions = list((deploy_state_path(package_dir).parent / "revisions").iterdir())
    assert len(revisions) == _RETAINED_DEPLOY_REVISIONS


@pytest.mark.parametrize(
    ("target_git_sha", "rollback_target"),
    [("first", "first"), (None, "0")],
)
def test_rollback_uses_archived_revision_and_records_new_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_git_sha: str | None,
    rollback_target: str,
) -> None:
    """Rollback deploys the selected immutable package and advances state history."""
    package_dir = tmp_path / ".build" / "demo"
    first_digest = "a" * 64
    second_digest = "b" * 64
    first_archive = package_dir.parent / ".deploy" / "demo" / "revisions" / first_digest
    second_archive = package_dir.parent / ".deploy" / "demo" / "revisions" / second_digest
    for archive, content in ((first_archive, "first\n"), (second_archive, "second\n")):
        archive.mkdir(parents=True)
        (archive / "agent.py").write_text(content, encoding="utf-8")
        (archive / "requirements.txt").write_text("example\n", encoding="utf-8")
        digest = archive.name
        (archive / "agentkit.lock.json").write_text(
            f'{{"packageDigest": "sha256:{digest}"}}',
            encoding="utf-8",
        )
    record_deploy(
        package_dir,
        resource_name="projects/p/locations/l/reasoningEngines/1",
        package_digest=f"sha256:{first_digest}",
        git_sha=target_git_sha,
        deployed_package_dir=first_archive,
    )
    record_deploy(
        package_dir,
        resource_name="projects/p/locations/l/reasoningEngines/1",
        package_digest=f"sha256:{second_digest}",
        git_sha="second",
        deployed_package_dir=second_archive,
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setenv("AGK_GIT_SHA", "current-environment")

    class FakeClient:
        def create(self, *, config: dict[str, object]) -> dict[str, str]:
            del config
            raise AssertionError("rollback must update the existing resource")

        def update(self, *, name: str, config: dict[str, object]) -> dict[str, str]:
            calls.append(config)
            return {"resourceName": name}

        def get(self, *, name: str) -> dict[str, str]:
            return {"resourceName": name}

    result = rollback_agent_engine(
        {},
        package_dir,
        project_id="p",
        location="l",
        target=rollback_target,
        client=FakeClient(),
    )

    assert result["status"] == "rolled_back"
    assert calls[0]["source_packages"] == [str(first_archive)]
    state = load_deploy_state(package_dir)
    assert state is not None
    assert state.package_digest == f"sha256:{first_digest}"
    assert state.git_sha == target_git_sha
    assert state.history[0].package_digest == f"sha256:{second_digest}"


def test_export_platform_dataset(hello_world_agent_dir: Path) -> None:
    """Export includes agent name even when no eval suites exist."""
    project = AgentProject.load(hello_world_agent_dir)
    exported = export_platform_dataset(project)
    assert exported["agentName"] == "hello-world"
    assert not exported["cases"]


def test_export_platform_dataset_honors_suite_filter(
    repo_root: Path,
) -> None:
    """Platform export includes only suites selected by the CLI filter."""
    project = AgentProject.load(repo_root / "examples" / "agent_platform")

    assert not export_platform_dataset(project, suite_filter="missing")["cases"]
    assert export_platform_dataset(project, suite_filter="smoke")["cases"]


def test_platform_judge_fields_are_export_only(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Judge settings survive export but fail before a Vertex client is constructed."""
    project = AgentProject.load(repo_root / "examples" / "agent_platform")
    entry = project.data.evals[0]
    raw = dict(entry["raw"])
    raw["cases"] = [
        {
            "name": "custom-judge",
            "input": "hello",
            "judge": {
                "promptTemplate": "Score this response",
                "judgeModel": "gemini-judge",
            },
        }
    ]
    project.data.evals = [{**entry, "raw": raw}]
    dataset = export_platform_dataset(project)
    client_calls = 0

    def fail_client(**_kwargs: object) -> object:
        nonlocal client_calls
        client_calls += 1
        raise AssertionError("Vertex client must not be constructed")

    monkeypatch.setitem(
        __import__("sys").modules,
        "vertexai",
        SimpleNamespace(Client=fail_client),
    )

    assert dataset["cases"][0]["judgePromptTemplate"] == "Score this response"
    assert dataset["cases"][0]["judgeModel"] == "gemini-judge"
    with pytest.raises(EvalError, match="custom-judge.*export only"):
        run_platform_eval_suite(
            dataset,
            project_id="p",
            location="l",
            resource_name="projects/p/locations/l/reasoningEngines/1",
        )
    assert client_calls == 0


def test_run_platform_eval_suite_maps_sdk_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Platform eval uses pinned SDK arguments and evaluates each configured threshold."""
    calls: dict[str, object] = {}

    class FakeEvals:
        def run_inference(self, **kwargs: object) -> str:
            calls["inference"] = kwargs
            return "inference-dataset"

        def evaluate(self, **kwargs: object) -> dict[str, object]:
            calls["evaluation"] = kwargs
            return {
                "eval_case_results": [
                    {
                        "response_candidate_results": [
                            {"metric_results": {"quality": {"score": 0.8}}}
                        ]
                    },
                    {
                        "response_candidate_results": [
                            {
                                "metric_results": {
                                    "general_quality_v1": {"error_message": "judge failed"}
                                }
                            }
                        ]
                    },
                    {
                        "response_candidate_results": [
                            {"metric_results": {"general_quality_v1": {"score": 0.1}}}
                        ]
                    },
                ]
            }

    fake_evals = FakeEvals()
    monkeypatch.setitem(
        __import__("sys").modules,
        "vertexai",
        SimpleNamespace(Client=lambda **_kwargs: SimpleNamespace(evals=fake_evals)),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "pandas",
        SimpleNamespace(DataFrame=lambda rows: rows),
    )
    dataset = {
        "cases": [
            {
                "name": "threshold",
                "suitePath": "evals/smoke.yaml",
                "prompt": "hello",
                "metric": "quality",
                "threshold": 0.9,
            },
            {
                "name": "error",
                "suitePath": "evals/smoke.yaml",
                "prompt": "hello again",
            },
            {
                "name": "no-threshold",
                "suitePath": "evals/smoke.yaml",
                "prompt": "low scores are valid without a threshold",
            },
        ]
    }

    result = run_platform_eval_suite(
        dataset,
        project_id="p",
        location="l",
        resource_name="projects/p/locations/l/reasoningEngines/1",
    )

    assert calls["inference"] == {
        "src": [
            {"prompt": "hello"},
            {"prompt": "hello again"},
            {"prompt": "low scores are valid without a threshold"},
        ],
        "agent": "projects/p/locations/l/reasoningEngines/1",
    }
    assert calls["evaluation"] == {
        "dataset": "inference-dataset",
        "metrics": [{"name": "quality"}, {"name": "general_quality_v1"}],
    }
    assert [case["passed"] for case in result["caseResults"]] == [False, False, True]
    assert "below threshold" in result["caseResults"][0]["failures"][0]
    assert "judge failed" in result["caseResults"][1]["failures"][0]


def test_compare_eval_results(tmp_path: Path) -> None:
    """Compare detects changed eval result files."""
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text('{"score": 1}', encoding="utf-8")
    candidate.write_text('{"score": 2}', encoding="utf-8")
    summary = compare_eval_results(baseline, candidate)
    assert summary["changed"] is True
