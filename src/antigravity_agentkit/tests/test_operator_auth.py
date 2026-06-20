"""Tests for operator-side service account impersonation."""

from __future__ import annotations

import pytest

from antigravity_agentkit.exceptions import AgentKitError
from antigravity_agentkit.operator_auth import (
    build_impersonated_credentials,
    operator_credentials_context,
    resolve_impersonate_target,
)


def test_resolve_impersonate_target_prefers_flag() -> None:
    """CLI flag wins over environment variable."""
    assert (
        resolve_impersonate_target(
            flag="flag-sa@proj.iam.gserviceaccount.com",
            env="env-sa@proj.iam.gserviceaccount.com",
        )
        == "flag-sa@proj.iam.gserviceaccount.com"
    )


def test_resolve_impersonate_target_uses_env_when_flag_missing() -> None:
    """Environment is used when CLI flag is absent."""
    assert (
        resolve_impersonate_target(
            flag=None,
            env="env-sa@proj.iam.gserviceaccount.com",
        )
        == "env-sa@proj.iam.gserviceaccount.com"
    )


def test_resolve_impersonate_target_returns_none_when_unset() -> None:
    """No impersonation target when flag and env are empty."""
    assert resolve_impersonate_target(flag=None, env=None) is None


def test_resolve_impersonate_target_strips_whitespace() -> None:
    """Targets are trimmed."""
    assert (
        resolve_impersonate_target(flag="  sa@p.iam.gserviceaccount.com  ", env=None)
        == "sa@p.iam.gserviceaccount.com"
    )


def test_resolve_impersonate_target_returns_none_for_blank_values() -> None:
    """Blank flag or env values are treated as unset."""
    assert resolve_impersonate_target(flag="   ", env=None) is None
    assert resolve_impersonate_target(flag=None, env="  ") is None


def test_build_impersonated_credentials_uses_google_auth() -> None:
    """Impersonated credentials delegate to google.auth.impersonated_credentials."""
    try:
        from google.auth import (
            credentials as auth_credentials,
            impersonated_credentials,  # type: ignore[import-untyped]
        )
    except ImportError:
        pytest.skip("google-auth not installed")

    source = auth_credentials.AnonymousCredentials()
    target = "target@proj.iam.gserviceaccount.com"
    creds = build_impersonated_credentials(target, source)
    assert isinstance(creds, impersonated_credentials.Credentials)
    assert creds.service_account_email == target


def test_operator_credentials_context_is_noop_without_target() -> None:
    """Context manager does nothing when impersonation is not requested."""
    try:
        import google.auth  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("google-auth not installed")

    original = google.auth.default
    with operator_credentials_context(None):
        assert google.auth.default is original
    assert google.auth.default is original


def test_operator_credentials_context_patches_default() -> None:
    """Context manager overrides google.auth.default while active."""
    try:
        import google.auth  # type: ignore[import-untyped]
        from google.auth import (
            credentials as auth_credentials,
            impersonated_credentials,  # type: ignore[import-untyped]
        )
    except ImportError:
        pytest.skip("google-auth not installed")

    source = auth_credentials.AnonymousCredentials()
    target = "target@proj.iam.gserviceaccount.com"
    original = google.auth.default

    def fake_default() -> tuple[auth_credentials.AnonymousCredentials, str | None]:
        return source, "fake-project"

    google.auth.default = fake_default  # type: ignore[assignment]
    try:
        with operator_credentials_context(target):
            patched_default, project = google.auth.default()
            assert project == "fake-project"
            assert isinstance(patched_default, impersonated_credentials.Credentials)
            assert patched_default.service_account_email == target
        assert google.auth.default is fake_default
    finally:
        google.auth.default = original


def test_operator_credentials_context_requires_adc() -> None:
    """Missing ADC raises AgentKitError when impersonation is requested."""
    try:
        import google.auth  # type: ignore[import-untyped]
        from google.auth.exceptions import DefaultCredentialsError  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("google-auth not installed")

    original = google.auth.default

    def failing_default() -> tuple[object, str | None]:
        raise DefaultCredentialsError("missing")

    google.auth.default = failing_default  # type: ignore[assignment]
    try:
        with (
            pytest.raises(AgentKitError, match="Application Default Credentials"),
            operator_credentials_context("sa@p.iam.gserviceaccount.com"),
        ):
            pass
    finally:
        google.auth.default = original
