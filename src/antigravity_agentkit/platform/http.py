"""Shared HTTP helpers for platform API calls."""

from __future__ import annotations

from typing import Any

from antigravity_agentkit.exceptions import DeployError

HTTP_ERROR_STATUS = 400


def authorized_gcp_session() -> Any:
    """Return a google-auth authorized requests session."""
    try:
        import google.auth  # type: ignore[import-untyped]
        import google.auth.transport.requests  # type: ignore[import-untyped]
        from google.auth.exceptions import DefaultCredentialsError  # type: ignore[import-untyped]
    except ImportError as exc:
        raise DeployError(
            "Live platform operations require the [gcp] extra: "
            "pip install 'antigravity-agentkit[gcp]'"
        ) from exc

    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    except (DefaultCredentialsError, OSError, ValueError) as exc:
        raise DeployError("GCP credentials are required for live platform operations.") from exc

    return google.auth.transport.requests.AuthorizedSession(credentials)
