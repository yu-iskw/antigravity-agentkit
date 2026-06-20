#!/usr/bin/env python3
"""Tier 2 — runtime embedding (requires antigravity-agentkit[antigravity] + API key)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from antigravity_agentkit import AgentProject
from antigravity_agentkit.runtime import (
    chat_response_text,
    create_agent_from_ir,
    create_agent_from_project,
)

AGENT_DIR = Path(__file__).resolve().parent / "agents" / "support-triage"

PROMPT = """
Classify this support message:
"Our billing export failed twice today. Can someone look at project acme-prod?"
Reply with category (answer, escalate, ticket, no-action) and one short sentence.
""".strip()


async def main_async() -> None:
    project = AgentProject.load(AGENT_DIR)
    ir = project.compile(production=True)

    agent = create_agent_from_ir(
        ir,
        project_root=project.root,
        interactive=False,
        loaded_skills=project.data.skills,
    )
    async with agent:
        response = await agent.chat(PROMPT)
        reply = await chat_response_text(response)
    print("create_agent_from_ir:", reply[:200])

    project_agent = create_agent_from_project(project, production=True, interactive=False)
    async with project_agent:
        response = await project_agent.chat(PROMPT)
        reply2 = await chat_response_text(response)
    print("create_agent_from_project:", reply2[:200])


def main() -> None:
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print("tier2_runtime: skip (set GEMINI_API_KEY or GOOGLE_API_KEY)")
        return

    asyncio.run(main_async())
    print("tier2_runtime: OK")


if __name__ == "__main__":
    main()
