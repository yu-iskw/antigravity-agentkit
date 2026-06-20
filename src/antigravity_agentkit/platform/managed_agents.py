"""Managed Agents API HTTP client for live registration."""

from __future__ import annotations

import json
import os
from typing import Any

from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.platform.http import HTTP_ERROR_STATUS

_MANAGED_AGENTS_URL = "https://generativelanguage.googleapis.com/v1beta/agents"
_API_REVISION = "2026-05-20"


def _managed_agents_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Api-Revision": _API_REVISION,
    }
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        headers["x-goog-api-key"] = api_key
        return headers

    token = os.environ.get("CLOUDSDK_AUTH_ACCESS_TOKEN")
    if not token:
        try:
            import google.auth  # type: ignore[import-untyped]
            import google.auth.transport.requests  # type: ignore[import-untyped]

            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/generative-language"],
            )
            credentials.refresh(google.auth.transport.requests.Request())
            token = credentials.token
        except Exception as exc:
            raise DeployError(
                "Managed Agents live deploy requires GEMINI_API_KEY, GOOGLE_API_KEY, or ADC."
            ) from exc
    headers["Authorization"] = f"Bearer {token}"
    return headers


def create_managed_agent(config: dict[str, Any]) -> dict[str, Any]:
    """POST gemini-agent-config to Managed Agents API."""
    try:
        import urllib3
    except ImportError as exc:
        raise DeployError(
            "Managed Agents live deploy requires urllib3 (install antigravity-agentkit[gcp])."
        ) from exc

    body = json.dumps(config).encode("utf-8")
    headers = _managed_agents_headers()
    http = urllib3.PoolManager()
    response = http.request(
        "POST",
        _MANAGED_AGENTS_URL,
        body=body,
        headers=headers,
        timeout=urllib3.Timeout(connect=10.0, read=120.0),
    )
    if response.status >= HTTP_ERROR_STATUS:
        detail = response.data.decode("utf-8", errors="replace")
        raise DeployError(f"Managed Agents API deploy failed ({response.status}): {detail}")

    payload = json.loads(response.data.decode("utf-8"))
    return {
        "status": "deployed",
        "agentId": payload.get("id", config.get("id", "")),
        "response": payload,
    }
