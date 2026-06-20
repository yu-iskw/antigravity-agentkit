"""Tests for python_embedding example scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_EXAMPLE_ROOT = Path(__file__).resolve().parents[3] / "examples" / "python_embedding"


def _run_example_main(script_name: str) -> None:
    script = _EXAMPLE_ROOT / script_name
    spec = importlib.util.spec_from_file_location(f"embedding_{script.stem}", script)
    if spec is None or spec.loader is None:
        msg = f"Could not load example script: {script}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def test_tier1_governance_script() -> None:
    _run_example_main("tier1_governance.py")


def test_tier3_deploy_script() -> None:
    _run_example_main("tier3_deploy.py")


def test_runtime_public_exports() -> None:
    from antigravity_agentkit.runtime import (
        create_agent_from_ir,
        create_agent_from_project,
        create_sdk_config_from_ir,
    )

    assert callable(create_agent_from_ir)
    assert callable(create_agent_from_project)
    assert callable(create_sdk_config_from_ir)


def test_agent_project_eval_method() -> None:
    from antigravity_agentkit import AgentProject

    project = AgentProject.load(_EXAMPLE_ROOT / "agents" / "support-triage")
    report = project.eval()
    assert report.success
