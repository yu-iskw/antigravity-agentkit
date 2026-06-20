#!/usr/bin/env python3
"""Slack-style embedding pattern (no slack-bolt dependency in this repo).

Copy this module into your Slack bot service and wire slack-bolt handlers to
``handle_app_mention``. Requires antigravity-agentkit[antigravity] and API keys.

Production tip: compile once at startup and reuse a long-lived Agent instance
(see ``_startup_agent``) instead of creating an agent per event.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from antigravity_agentkit import AgentProject
from antigravity_agentkit.runtime import chat_response_text, create_agent_from_project

AGENT_DIR = Path(__file__).resolve().parent / "agents" / "support-triage"

_project = AgentProject.load(AGENT_DIR)


def _startup_agent() -> Any:
    """Create the agent once at application startup (FastAPI lifespan, bolt startup)."""
    return create_agent_from_project(_project, production=True, interactive=False)


def _mention_prompt(event: dict[str, Any]) -> str:
    user = event.get("user", "unknown")
    text = event.get("text", "")
    return f"""
You are responding to a Slack mention.
Slack user: {user}
Message:
{text}

Decide whether this needs:
- an immediate answer,
- escalation,
- a ticket,
- or no action.
""".strip()


async def handle_app_mention(event: dict[str, Any], *, agent: Any) -> str:
    """Classify a Slack app_mention event and return assistant text."""
    async with agent:
        response = await agent.chat(_mention_prompt(event))
        return await chat_response_text(response)


async def _demo() -> None:
    agent = _startup_agent()
    sample = {
        "user": "U123",
        "text": "<@BOT> The staging deploy is red since 09:00 UTC.",
    }
    reply = await handle_app_mention(sample, agent=agent)
    print(reply)


def main() -> None:
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print("slack_bot_pattern: skip live demo (set GEMINI_API_KEY or GOOGLE_API_KEY)")
        print("Import handle_app_mention from this module in your slack-bolt app.")
        return
    asyncio.run(_demo())
    print("slack_bot_pattern: OK")


if __name__ == "__main__":
    main()
