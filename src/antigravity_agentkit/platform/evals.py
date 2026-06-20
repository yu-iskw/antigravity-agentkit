"""Agent Platform evaluation helpers."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from antigravity_agentkit.evals import _suite_matches_filter
from antigravity_agentkit.exceptions import EvalError
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.evals import EvalCase, EvalSuite

_DEFAULT_PLATFORM_METRIC = "general_quality_v1"
_JUDGE_PROMPT_KEY = "judgePromptTemplate"
_JUDGE_MODEL_KEY = "judgeModel"


def _case_has_judge_export(case: dict[str, Any]) -> bool:
    return _JUDGE_PROMPT_KEY in case or _JUDGE_MODEL_KEY in case


def _judge_export_error(case_name: str) -> EvalError:
    return EvalError(
        f"Platform eval case {case_name!r} uses judge "
        "configuration, which is currently supported for dataset export only."
    )


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
        exported[_JUDGE_PROMPT_KEY] = case.judge.prompt_template
    if case.judge.judge_model:
        exported[_JUDGE_MODEL_KEY] = case.judge.judge_model
    return exported


def export_platform_dataset(
    project: AgentProject,
    suite_filter: str | None = None,
) -> dict[str, Any]:
    """Export AgentKit eval cases to a Platform-compatible dataset JSON."""
    cases: list[dict[str, Any]] = []
    for entry in project.data.evals:
        suite_path = str(entry.get("path", "unknown"))
        if not _suite_matches_filter(suite_path, suite_filter):
            continue
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
    if hasattr(evaluation, "model_dump"):
        return evaluation.model_dump(mode="json", exclude_none=True)
    if hasattr(evaluation, "to_dict"):
        return evaluation.to_dict()
    if isinstance(evaluation, dict):
        return evaluation
    return str(evaluation)


def _metric_result(
    case_result: dict[str, Any],
    metric: str,
) -> dict[str, Any] | None:
    candidates = case_result.get("response_candidate_results") or []
    if not candidates or not isinstance(candidates[0], dict):
        return None
    metric_results = candidates[0].get("metric_results") or {}
    if not isinstance(metric_results, dict):
        return None
    selected = metric_results.get(metric)
    if isinstance(selected, dict):
        return selected
    return None


def _metric_error_text(metric_result: dict[str, Any]) -> str | None:
    """Return human-readable text from a pinned Vertex MetricResult error field."""
    error = metric_result.get("error")
    if error is None:
        return None
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            return str(message)
        return str(error)
    return str(error)


def _case_summary(
    case: dict[str, Any],
    result: dict[str, Any] | None,
) -> dict[str, Any]:
    metric = str(case.get("metric") or _DEFAULT_PLATFORM_METRIC)
    threshold = case.get("threshold")
    failures: list[str] = []
    metric_result = _metric_result(result or {}, metric)
    score: float | None = None
    if metric_result is None:
        failures.append(f"Platform evaluation returned no result for metric {metric!r}.")
    else:
        error_text = _metric_error_text(metric_result)
        raw_score = metric_result.get("score")
        if error_text:
            failures.append(f"Platform evaluation error: {error_text}")
        elif isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool):
            score = float(raw_score)
        else:
            failures.append(f"Platform evaluation returned no score for metric {metric!r}.")
        if score is not None and threshold is not None and score < float(threshold):
            failures.append(f"Metric {metric!r} score {score:g} is below threshold {threshold}.")

    return {
        "name": str(case["name"]),
        "suitePath": str(case["suitePath"]),
        "metric": metric,
        "score": score,
        "threshold": threshold,
        "passed": not failures,
        "failures": failures,
    }


def run_platform_eval_suite(
    dataset: dict[str, Any],
    *,
    project_id: str,
    location: str,
    resource_name: str,
) -> dict[str, Any]:
    """Run Platform eval inference + grading against a deployed agent."""
    cases = dataset.get("cases", [])
    if not cases:
        raise EvalError("Platform eval dataset has no cases.")
    for case in cases:
        if _case_has_judge_export(case):
            case_name = case.get("name", "<unknown>")
            raise _judge_export_error(str(case_name))

    try:
        import vertexai  # type: ignore[import-untyped]
    except ImportError as exc:
        raise EvalError(
            "Platform eval requires the [gcp] extra: pip install 'antigravity-agentkit[gcp]'"
        ) from exc

    client = vertexai.Client(project=project_id, location=location)
    evals_api = client.evals

    try:
        pandas = importlib.import_module("pandas")
    except ImportError as exc:
        raise EvalError(
            "Platform eval requires the [gcp] evaluation dependencies: "
            "pip install 'antigravity-agentkit[gcp]'"
        ) from exc

    rows: list[dict[str, Any]] = []
    metrics: list[str] = []
    for case in cases:
        row = {"prompt": case["prompt"]}
        if case.get("referenceAnswer"):
            row["reference"] = case["referenceAnswer"]
        rows.append(row)
        metric = str(case.get("metric") or _DEFAULT_PLATFORM_METRIC)
        if metric not in metrics:
            metrics.append(metric)

    inference = evals_api.run_inference(
        src=pandas.DataFrame(rows),
        agent=resource_name,
    )
    evaluation = evals_api.evaluate(
        dataset=inference,
        metrics=[{"name": metric} for metric in metrics],
    )
    serialized = _serialize_eval_result(evaluation)
    if not isinstance(serialized, dict):
        raise EvalError("Platform evaluation returned an unsupported result payload.")
    raw_case_results = serialized.get("eval_case_results") or []
    case_results = [
        _case_summary(
            case,
            raw_case_results[index]
            if index < len(raw_case_results) and isinstance(raw_case_results[index], dict)
            else None,
        )
        for index, case in enumerate(cases)
    ]
    return {
        "status": "completed",
        "metrics": metrics,
        "resourceName": resource_name,
        "caseCount": len(cases),
        "caseResults": case_results,
        "results": serialized,
    }


def _case_count(payload: dict[str, Any]) -> int:
    if "caseResults" in payload:
        return len(payload["caseResults"])
    if "eval_case_results" in payload:
        return len(payload["eval_case_results"])
    cases = payload.get("cases")
    if isinstance(cases, list):
        return len(cases)
    results = payload.get("results")
    if isinstance(results, list):
        return len(results)
    return 0


def compare_eval_results(baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    """Compare two Platform eval result JSON files."""
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    return {
        "baseline": baseline_path.name,
        "candidate": candidate_path.name,
        "baselineCaseCount": _case_count(baseline),
        "candidateCaseCount": _case_count(candidate),
        "changed": baseline != candidate,
    }
