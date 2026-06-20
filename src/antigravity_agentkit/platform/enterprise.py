"""Gemini Enterprise catalog publish."""

from __future__ import annotations

from typing import Any

from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.platform.http import HTTP_ERROR_STATUS, authorized_gcp_session


def publish_to_gemini_enterprise(
    *,
    project_id: str,
    location: str,
    resource_name: str,
    registry_name: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Publish a deployed Agent Runtime instance to Gemini Enterprise catalog."""
    session = authorized_gcp_session()
    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/publishers/google/models/gemini-enterprise:catalogEntries"
    )
    payload: dict[str, Any] = {
        "runtimeResource": resource_name,
        "publishMode": "ADK",
    }
    if registry_name:
        payload["agentRegistryName"] = registry_name
    if display_name:
        payload["displayName"] = display_name

    response = session.post(url, json=payload, timeout=120)
    if response.status_code >= HTTP_ERROR_STATUS:
        raise DeployError(
            f"Gemini Enterprise publish failed ({response.status_code}): {response.text}"
        )

    body = response.json() if response.content else {}
    return {
        "status": "published",
        "catalogEntry": body.get("name", ""),
        "resourceName": resource_name,
        "registryName": registry_name,
    }
