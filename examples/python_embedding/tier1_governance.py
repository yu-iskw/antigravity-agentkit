#!/usr/bin/env python3
"""Tier 1 — core-only governance (no google-antigravity, no GCP, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

from antigravity_agentkit import AgentProject

AGENT_DIR = Path(__file__).resolve().parent / "agents" / "support-triage"


def main() -> None:
    project = AgentProject.load(AGENT_DIR)
    ir = project.compile(production=True)

    if ir.capabilities.mode != "restricted":
        print(f"expected restricted capabilities, got {ir.capabilities.mode!r}", file=sys.stderr)
        raise SystemExit(1)
    if ir.schema_version != "antigravity-agentkit.ir/v1alpha1":
        print(f"unexpected schema version: {ir.schema_version!r}", file=sys.stderr)
        raise SystemExit(1)
    if "triage-helper" not in {skill.name for skill in ir.skills}:
        print("expected triage-helper skill in IR", file=sys.stderr)
        raise SystemExit(1)

    report = project.eval()
    print(f"eval: {report.passed}/{report.total} passed")
    if report.total == 0:
        print("expected at least one eval case for support-triage", file=sys.stderr)
        raise SystemExit(1)
    if not report.success:
        raise SystemExit(1)

    print("tier1_governance: OK")


if __name__ == "__main__":
    main()
