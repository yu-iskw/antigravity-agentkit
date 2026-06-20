"""Agent Platform evaluation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from antigravity_agentkit.exceptions import EvalError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.evals import EvalCase, EvalSuite

EvalMode = Literal["mock", "live", "platform"]


def _export_case(suite_path: str, case: EvalCase) -> dict[str, Any]:
    exported: dict[str, Any] = {
        "name": case.name,
        "suitePath": suite_path,
        "prompt": case.input,
    }
    if case.expected.reference_answer:
        exported["referenceAnswer"] = case.expected.reference_answer
    if case.expected.metric:
        exported["metric"] = case.expected.metric
    if case.expected.threshold is not None:
        exported["threshold"] = case.expected.threshold
    if case.judge.prompt_template:
        exported["judgePromptTemplate"] = case.judge.prompt_template
    if case.judge.judge_model:
        exported["judgeModel"] = case.judge.judge_model
    return exported


def export_platform_dataset(project: AgentProject) -> dict[str, Any]:
    """Export AgentKit eval cases to a Platform-compatible dataset JSON."""
    cases: list[dict[str, Any]] = []
    for entry in project.data.evals:
        suite_path = str(entry.get("path", "unknown"))
        raw = entry.get("raw", entry.get("suite", {}))
        suite = EvalSuite.from_dict(raw)
        for case in suite.cases:
            cases.append(_export_case(suite_path, case))

    return {
        "schemaVersion": "antigravity-agentkit.eval-export/v1",
        "agentName": project.manifest.metadata.name,
        "cases": cases,
    }


def write_platform_dataset(project: AgentProject, output_path: Path) -> Path:
    """Write exported Platform dataset JSON to disk."""
    payload = export_platform_dataset(project)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def _serialize_eval_result(evaluation: Any) -> Any:
    if hasattr(evaluation, "to_dict"):
        return evaluation.to_dict()
    if isinstance(evaluation, dict):
        return evaluation
    return str(evaluation)


def run_platform_eval_suite(
    dataset: dict[str, Any],
    *,
    project_id: str,
    location: str,
    resource_name: str,
    metric: str = "general_quality",
) -> dict[str, Any]:
    """Run Platform eval inference + grading against a deployed agent."""
    try:
        import vertexai  # type: ignore[import-untyped]
    except ImportError as exc:
        raise EvalError(
            "Platform eval requires the [gcp] extra: pip install 'antigravity-agentkit[gcp]'"
        ) from exc

    client = vertexai.Client(project=project_id, location=location)
    evals_api = client.evals

    scenarios = [
        {"prompt": case["prompt"], "name": case["name"]} for case in dataset.get("cases", [])
    ]
    if not scenarios:
        raise EvalError("Platform eval dataset has no cases.")

    inference = evals_api.run_inference(
        agent_resource=resource_name,
        scenarios=scenarios,
    )
    evaluation = evals_api.evaluate(
        inference_results=inference,
        metrics=[metric],
    )
    return {
        "status": "completed",
        "metric": metric,
        "resourceName": resource_name,
        "caseCount": len(scenarios),
        "results": _serialize_eval_result(evaluation),
    }


def compare_eval_results(baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    """Compare two Platform eval result JSON files."""
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    return {
        "baseline": baseline_path.name,
        "candidate": candidate_path.name,
        "baselineCaseCount": len(baseline.get("cases", baseline.get("results", []))),
        "candidateCaseCount": len(candidate.get("cases", candidate.get("results", []))),
        "changed": baseline != candidate,
    }
