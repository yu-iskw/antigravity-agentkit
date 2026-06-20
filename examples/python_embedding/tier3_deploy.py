#!/usr/bin/env python3
"""Tier 3 — deployment emitters (requires antigravity-agentkit[gcp] for ship helpers)."""

from __future__ import annotations

import sys
from pathlib import Path

from antigravity_agentkit import AgentProject, build_deployment_config, load_deployment

AGENT_DIR = Path(__file__).resolve().parent / "agents" / "support-triage"
PROJECT_ID = "demo-project"
LOCATION = "asia-northeast1"


def main() -> None:
    project = AgentProject.load(AGENT_DIR)
    deployment = load_deployment(AGENT_DIR)

    config = build_deployment_config(
        project=project,
        deployment=deployment,
        project_id=PROJECT_ID,
        location=LOCATION,
    )

    target = config.get("target")
    if target != "agent-platform-runtime":
        print(f"unexpected target: {target!r}", file=sys.stderr)
        raise SystemExit(1)
    if "source_packages" not in config or "display_name" not in config:
        print("deployment config missing required keys", file=sys.stderr)
        raise SystemExit(1)

    print("target:", deployment.spec.target)
    print("agent-platform config keys:", sorted(config.keys()))
    print("tier3_deploy: OK")


if __name__ == "__main__":
    main()
