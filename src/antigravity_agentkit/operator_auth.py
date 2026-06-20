"""Operator-side GCP credentials for local CLI runs (impersonation)."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from antigravity_agentkit.exceptions import AgentKitError

IMPERSONATE_ENV = "AGK_IMPERSONATE_SERVICE_ACCOUNT"
CLOUD_PLATFORM_SCOPE = ("https://www.googleapis.com/auth/cloud-platform",)
_GOOGLE_AUTH_REQUIRED_MSG = (
    "google-auth is required for service account impersonation; "
    "install with pip install 'antigravity-agentkit[antigravity]'"
)


def resolve_impersonate_target(
    *,
    flag: str | None = None,
    env: str | None = None,
) -> str | None:
    """Return impersonation target; CLI flag wins over environment."""
    if flag:
        stripped = flag.strip()
        return stripped or None
    effective_env = env if env is not None else os.environ.get(IMPERSONATE_ENV)
    if effective_env:
        stripped = effective_env.strip()
        return stripped or None
    return None


def build_impersonated_credentials(
    target_principal: str,
    source_credentials: Any,
) -> Any:
    """Build impersonated credentials from a source credential object."""
    try:
        from google.auth import impersonated_credentials  # type: ignore[import-untyped]
    except ImportError as exc:
        raise AgentKitError(_GOOGLE_AUTH_REQUIRED_MSG) from exc

    return impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=target_principal,
        target_scopes=list(CLOUD_PLATFORM_SCOPE),
    )


def _load_source_credentials() -> tuple[Any, str | None]:
    """Load application-default credentials."""
    try:
        import google.auth  # type: ignore[import-untyped]
        from google.auth.exceptions import DefaultCredentialsError  # type: ignore[import-untyped]
    except ImportError as exc:
        raise AgentKitError(_GOOGLE_AUTH_REQUIRED_MSG) from exc

    try:
        return google.auth.default()
    except (DefaultCredentialsError, OSError, ValueError) as exc:
        msg = (
            "Application Default Credentials are required to impersonate a service account. "
            "Run `gcloud auth application-default login` or set GOOGLE_APPLICATION_CREDENTIALS."
        )
        raise AgentKitError(msg) from exc


@contextmanager
def operator_credentials_context(impersonate: str | None) -> Generator[None, None, None]:
    """Temporarily override google.auth.default() with impersonated credentials."""
    if not impersonate:
        yield
        return

    source_credentials, project = _load_source_credentials()
    target_credentials = build_impersonated_credentials(impersonate, source_credentials)

    import google.auth  # type: ignore[import-untyped]

    original_default = google.auth.default

    def _impersonated_default(
        scopes: Any = None,
        request: Any = None,
        quota_project_id: Any = None,
        default_scopes: Any = None,
    ) -> tuple[Any, str | None]:
        del scopes, request, default_scopes
        return target_credentials, quota_project_id or project

    google.auth.default = _impersonated_default
    try:
        yield
    finally:
        google.auth.default = original_default


__all__ = [
    "CLOUD_PLATFORM_SCOPE",
    "IMPERSONATE_ENV",
    "build_impersonated_credentials",
    "operator_credentials_context",
    "resolve_impersonate_target",
]
