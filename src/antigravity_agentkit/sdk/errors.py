"""SDK compatibility errors."""

from __future__ import annotations

from antigravity_agentkit.exceptions import CompilationError
from antigravity_agentkit.json_types import JsonValue

ANTIGRAVITY_INSTALL_HINT = (
    "google-antigravity is not installed; install with "
    "pip install 'antigravity-agentkit[antigravity]'"
)


class SdkCompatibilityError(CompilationError):
    """Raised when the installed SDK cannot represent a compiled IR feature."""

    def __init__(
        self,
        message: str,
        *,
        feature: str,
        sdk_version: str | None,
        install_hint: str = ANTIGRAVITY_INSTALL_HINT,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.feature = feature
        self.sdk_version = sdk_version
        self.install_hint = install_hint
        self.details = details or {}
