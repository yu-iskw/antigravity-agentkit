"""Deploy target name aliases."""

from __future__ import annotations

_CANONICAL_TARGETS: dict[str, str] = {
    "agent-platform": "agent-platform-runtime",
    "agent-platform-runtime": "agent-platform-runtime",
    "gemini-api": "managed-agents-api",
    "managed-agents-api": "managed-agents-api",
}


def resolve_target_name(name: str) -> str:
    """Resolve a user-facing deploy target to its canonical internal name."""
    canonical = _CANONICAL_TARGETS.get(name)
    if canonical is None:
        return name
    return canonical


def supported_target_aliases() -> dict[str, str]:
    """Return the alias map for supported deploy targets."""
    return dict(_CANONICAL_TARGETS)
