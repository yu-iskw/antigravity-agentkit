"""Tests for evaluation runner mock mode."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from antigravity_agentkit.evals import assert_evals_passed, run_evals
from antigravity_agentkit.exceptions import EvalError
from antigravity_agentkit.project import AgentProject


def test_run_evals_mock_mode_passes_mcp_smoke(mcp_agent_dir: Path) -> None:
    """mcp example smoke eval passes in deterministic mock mode."""
    project = AgentProject.load(mcp_agent_dir)
    result = run_evals(project)

    assert result.total == 1
    assert result.passed == 1
    assert result.failed == 0
    assert result.success
    assert result.cases[0].name == "current-time"
    assert result.cases[0].mock_tools == ["mcp.clock.get_utc_time"]


def test_run_evals_live_mode_requires_explicit_argument(
    mcp_agent_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default execution stays mock while an explicit live mode uses the runtime."""
    project = AgentProject.load(mcp_agent_dir)
    run_chat = AsyncMock(return_value="The current UTC time is available.")
    monkeypatch.setattr(
        "antigravity_agentkit.runtime.RuntimeAgent.run_chat",
        run_chat,
    )

    mock_result = run_evals(project)
    live_result = run_evals(project, mode="live")

    assert mock_result.cases[0].mock_tools == ["mcp.clock.get_utc_time"]
    assert live_result.total == 1
    run_chat.assert_awaited_once()


def test_run_evals_platform_mode_requires_explicit_argument(
    mcp_agent_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit platform mode dispatches the selected cases to Platform eval."""
    project = AgentProject.load(mcp_agent_dir)
    calls = 0

    def fake_run_platform_eval_suite(
        dataset: dict[str, Any],
        **_kwargs: object,
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        case = dataset["cases"][0]
        return {
            "caseResults": [
                {
                    "name": case["name"],
                    "suitePath": case["suitePath"],
                    "passed": True,
                    "failures": [],
                }
            ]
        }

    monkeypatch.setattr(
        "antigravity_agentkit.platform.evals.run_platform_eval_suite",
        fake_run_platform_eval_suite,
    )

    mock_result = run_evals(project)
    platform_result = run_evals(
        project,
        mode="platform",
        resource_name="projects/p/locations/l/reasoningEngines/1",
        project_id="p",
        location="l",
    )

    assert mock_result.total == 1
    assert platform_result.passed == 1
    assert calls == 1


def test_mock_eval_fails_for_missing_required_phrase(mcp_agent_dir: Path) -> None:
    """Mock responses do not copy must-mention expectations into their output."""
    project = AgentProject.load(mcp_agent_dir)
    entry = project.data.evals[0]
    raw = dict(entry["raw"])
    raw["cases"] = [
        {
            "name": "missing-phrase",
            "input": "What is the current UTC time?",
            "expected": {"mustMention": ["unattainable-phrase"]},
        }
    ]
    project.data.evals = [{**entry, "raw": raw}]

    result = run_evals(project)

    assert result.failed == 1
    assert "unattainable-phrase" in result.cases[0].failures[0]


def test_run_evals_suite_filter(mcp_agent_dir: Path) -> None:
    """Suite filter matches by filename stem."""
    project = AgentProject.load(mcp_agent_dir)

    smoke_result = run_evals(project, suite_filter="smoke")
    missing_result = run_evals(project, suite_filter="integration")

    assert smoke_result.total == 1
    assert missing_result.total == 0


def test_run_evals_empty_when_no_eval_files(hello_world_agent_dir: Path) -> None:
    """Agents without evals return an empty successful result."""
    project = AgentProject.load(hello_world_agent_dir)
    result = run_evals(project)

    assert result.total == 0
    assert result.success


def test_assert_evals_passed_raises_on_failure(mcp_agent_dir: Path) -> None:
    """assert_evals_passed raises EvalError when cases fail."""
    project = AgentProject.load(mcp_agent_dir)
    result = run_evals(project)
    result.cases[0].passed = False
    result.cases[0].failures = ["forced failure"]
    result.passed = 0
    result.failed = 1

    with pytest.raises(EvalError, match="Evaluation failures"):
        assert_evals_passed(result)


def test_assert_evals_passed_succeeds_when_all_pass(mcp_agent_dir: Path) -> None:
    """assert_evals_passed is a no-op when all cases pass."""
    project = AgentProject.load(mcp_agent_dir)
    result = run_evals(project)

    assert_evals_passed(result)
