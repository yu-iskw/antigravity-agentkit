"""Live Agent Registry and Skill Registry operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from antigravity_agentkit.exceptions import DeployError
from antigravity_agentkit.platform.http import HTTP_ERROR_STATUS, authorized_gcp_session


def _registry_base_url(location: str) -> str:
    return f"https://{location}-aiplatform.googleapis.com/v1"


def register_agent_live(
    metadata: dict[str, Any],
    *,
    project_id: str,
    location: str,
    resource_name: str | None = None,
) -> dict[str, Any]:
    """Register agent metadata with regional Agent Registry."""
    session = authorized_gcp_session()
    parent = f"projects/{project_id}/locations/{location}"
    url = f"{_registry_base_url(location)}/{parent}/agents"

    payload = dict(metadata)
    if resource_name:
        payload["runtimeResource"] = resource_name

    response = session.post(url, json=payload, timeout=120)
    if response.status_code >= HTTP_ERROR_STATUS:
        raise DeployError(
            f"Agent Registry registration failed ({response.status_code}): {response.text}"
        )

    body = response.json() if response.content else {}
    agent_name = body.get("name", "")
    return {
        "status": "registered",
        "registryName": agent_name,
        "resourceName": resource_name,
        "metadata": metadata,
    }


def publish_skill_live(
    *,
    project_id: str,
    location: str,
    skill_name: str,
    zip_path: Path,
    sha256: str,
) -> dict[str, Any]:
    """Upload a skill zip to Skill Registry."""
    session = authorized_gcp_session()
    parent = f"projects/{project_id}/locations/{location}"
    url = f"{_registry_base_url(location)}/{parent}/skills"

    zip_bytes = zip_path.read_bytes()
    metadata = {
        "name": skill_name,
        "contentHash": sha256,
    }
    files = {
        "metadata": (None, json.dumps(metadata), "application/json"),
        "content": (zip_path.name, zip_bytes, "application/zip"),
    }
    response = session.post(url, files=files, timeout=300)
    if response.status_code >= HTTP_ERROR_STATUS:
        raise DeployError(f"Skill Registry upload failed ({response.status_code}): {response.text}")

    body = response.json() if response.content else {}
    revision = body.get("name", "")
    registry_ref = f"projects/{project_id}/locations/{location}/skills/{skill_name}"
    return {
        "status": "published",
        "registryRef": registry_ref,
        "revision": revision,
        "sha256": sha256,
        "zipPath": str(zip_path),
    }
