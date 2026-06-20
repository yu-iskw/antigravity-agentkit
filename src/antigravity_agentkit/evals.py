"""Evaluation runner with deterministic mock-mode assertions."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Literal

from antigravity_agentkit.exceptions import EvalError
from antigravity_agentkit.policies import resolve_tool_decision
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.evals import EvalCase, EvalSuite

EvalRunMode = Literal["mock", "live", "platform"]


@dataclass
class EvalCaseResult:
    """Result of a single evaluation case."""

    name: str
    suite_path: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    mock_response: str = ""
    mock_tools: list[str] = field(default_factory=list)


@dataclass
class EvalRunResult:
    """Aggregate result of an evaluation run."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    cases: list[EvalCaseResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return True when all cases passed."""
        return self.failed == 0


def _suite_matches_filter(suite_path: str, suite_filter: str | None) -> bool:
    """Return True when the suite path matches an optional filter expression."""
    if not suite_filter:
        return True
    stem = suite_path.rsplit("/", maxsplit=1)[-1].lower()
    for token in suite_filter.split(","):
        needle = token.strip().lower()
        if needle and needle in stem:
            return True
    return False


def _mock_agent_response(project: AgentProject, case: EvalCase) -> tuple[str, list[str]]:
    """Return deterministic mock response text and tool names for eval checks."""
    instructions = project.data.system_instructions.lower()
    response_parts = [f"Processing request: {case.input}"]

    for token in re.findall(r"[a-z]{3,}", case.input.lower()):
        if token in instructions:
            response_parts.append(token)

    response_parts.append("dataset table metadata summary")
    response_text = " ".join(response_parts)

    mock_tools: list[str] = []
    if case.tools.allowed:
        mock_tools.append(case.tools.allowed[0])
    elif project.data.mcp_config:
        mock_tools.append("read_skill")

    return response_text, mock_tools


def _check_mentions(response: str, expected: list[str], *, required: bool) -> list[str]:
    """Check must-mention or must-not-mention assertions."""
    failures: list[str] = []
    lowered = response.lower()
    for phrase in expected:
        found = phrase.lower() in lowered
        if required and not found:
            failures.append(f"Expected response to mention {phrase!r}")
        if not required and found:
            failures.append(f"Expected response not to mention {phrase!r}")
    return failures


def _check_forbidden_patterns(response: str, patterns: list[str]) -> list[str]:
    """Check regex forbidden patterns in the mock response."""
    failures: list[str] = []
    for pattern in patterns:
        if re.search(pattern, response, flags=re.IGNORECASE):
            failures.append(f"Response matched forbidden pattern: {pattern!r}")
    return failures


def _check_tool_constraints(
    project: AgentProject,
    case: EvalCase,
    tools_used: list[str],
) -> list[str]:
    """Check allowed/denied tool constraints using policy resolution."""
    failures: list[str] = []
    policies = project.data.policies

    for tool in tools_used:
        if case.tools.denied and tool in case.tools.denied:
            failures.append(f"Denied tool was used: {tool!r}")
        if case.tools.allowed and tool not in case.tools.allowed:
            failures.append(f"Tool {tool!r} is not in allowed list")

    if policies:
        from antigravity_agentkit.policies import parse_policies_dict

        doc = parse_policies_dict(policies)
        for tool in tools_used:
            decision = resolve_tool_decision(tool, doc)
            if decision == "deny":
                failures.append(f"Policy denies tool: {tool!r}")

    if case.expected.max_tool_calls is not None and len(tools_used) > case.expected.max_tool_calls:
        failures.append(
            f"Tool call count {len(tools_used)} exceeds max {case.expected.max_tool_calls}"
        )

    return failures


def _run_case_mock(
    project: AgentProject,
    suite_path: str,
    case: EvalCase,
) -> EvalCaseResult:
    """Run a single eval case in mock mode."""
    response, tools_used = _mock_agent_response(project, case)
    failures: list[str] = []
    failures.extend(_check_mentions(response, case.expected.must_mention, required=True))
    failures.extend(_check_mentions(response, case.expected.must_not_mention, required=False))
    failures.extend(_check_forbidden_patterns(response, case.expected.forbidden_patterns))
    failures.extend(_check_tool_constraints(project, case, tools_used))

    return EvalCaseResult(
        name=case.name,
        suite_path=suite_path,
        passed=not failures,
        failures=failures,
        mock_response=response,
        mock_tools=tools_used,
    )


async def _run_live_cases(
    project: AgentProject,
    items: list[tuple[str, EvalCase]],
) -> list[EvalCaseResult]:
    """Run eval cases against one live SDK agent instance."""
    from antigravity_agentkit.runtime import RuntimeAgent

    runtime = RuntimeAgent(project)
    results: list[EvalCaseResult] = []
    for suite_path, case in items:
        started = time.monotonic()
        response_text = await runtime.run_chat(case.input)
        elapsed = time.monotonic() - started

        failures: list[str] = []
        failures.extend(_check_mentions(response_text, case.expected.must_mention, required=True))
        failures.extend(
            _check_mentions(response_text, case.expected.must_not_mention, required=False)
        )
        failures.extend(_check_forbidden_patterns(response_text, case.expected.forbidden_patterns))
        if (
            case.expected.max_latency_seconds is not None
            and elapsed > case.expected.max_latency_seconds
        ):
            failures.append(
                f"Latency {elapsed:.2f}s exceeds max {case.expected.max_latency_seconds}s"
            )
        if case.expected.reference_answer and (
            case.expected.reference_answer.lower() not in response_text.lower()
        ):
            failures.append("Response did not match reference answer substring.")

        results.append(
            EvalCaseResult(
                name=case.name,
                suite_path=suite_path,
                passed=not failures,
                failures=failures,
                mock_response=response_text,
                mock_tools=[],
            )
        )
    return results


def _run_case(
    project: AgentProject,
    suite_path: str,
    case: EvalCase,
    *,
    mode: EvalRunMode,
) -> EvalCaseResult:
    """Dispatch eval case execution by mode (mock only; live uses batch runner)."""
    if mode == "mock":
        return _run_case_mock(project, suite_path, case)
    raise EvalError(f"Unsupported eval mode for single-case runner: {mode}")


def run_evals(  # noqa: PLR0913
    project: AgentProject,
    suite_filter: str | None = None,
    *,
    mode: EvalRunMode | None = None,
    resource_name: str | None = None,
    project_id: str | None = None,
    location: str | None = None,
) -> EvalRunResult:
    """Run evaluation suites using mock, live, or platform mode."""
    if mode == "platform":
        if not resource_name or not project_id or not location:
            raise EvalError("Platform eval requires --resource-name, --project, and --location.")
        from antigravity_agentkit.platform.evals import (
            export_platform_dataset,
            run_platform_eval_suite,
        )

        dataset = export_platform_dataset(project)
        platform_result = run_platform_eval_suite(
            dataset,
            project_id=project_id,
            location=location,
            resource_name=resource_name,
        )
        result = EvalRunResult(total=1, passed=1 if platform_result["status"] == "completed" else 0)
        if platform_result["status"] != "completed":
            result.failed = 1
            result.passed = 0
            result.cases.append(
                EvalCaseResult(
                    name="platform-suite",
                    suite_path="platform",
                    passed=False,
                    failures=[str(platform_result)],
                )
            )
        return result

    result = EvalRunResult()
    eval_entries = project.data.evals
    if not eval_entries:
        return result

    for entry in eval_entries:
        suite_path = str(entry.get("path", "unknown"))
        if not _suite_matches_filter(suite_path, suite_filter):
            continue

        raw = entry.get("raw", entry.get("suite", {}))
        suite = EvalSuite.from_dict(raw)
        suite_mode: EvalRunMode = mode or suite.mode
        if suite_mode == "live":
            live_items = [(suite_path, case) for case in suite.cases]
            case_results = asyncio.run(_run_live_cases(project, live_items))
            for case_result in case_results:
                result.cases.append(case_result)
                result.total += 1
                if case_result.passed:
                    result.passed += 1
                else:
                    result.failed += 1
            continue
        for case in suite.cases:
            case_result = _run_case(project, suite_path, case, mode=suite_mode)
            result.cases.append(case_result)
            result.total += 1
            if case_result.passed:
                result.passed += 1
            else:
                result.failed += 1

    return result


def assert_evals_passed(result: EvalRunResult) -> None:
    """Raise EvalError when any evaluation case failed."""
    if result.success:
        return
    separator = "; "
    messages = [
        f"{item.suite_path}:{item.name}: {separator.join(item.failures)}"
        for item in result.cases
        if not item.passed
    ]
    raise EvalError("Evaluation failures:\n" + "\n".join(messages))
