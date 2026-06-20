"""Typed exceptions for Antigravity AgentKit."""

from __future__ import annotations


class AgentKitError(Exception):
    """Base exception for all AgentKit errors."""


class LoadError(AgentKitError):
    """Raised when loading agent source files fails."""


class ValidationError(AgentKitError):
    """Raised when agent configuration fails schema or security validation."""


class SecurityValidationError(ValidationError):
    """Raised when security validation fails."""


class CompileError(AgentKitError):
    """Raised when compilation to Antigravity runtime objects fails."""


# Backward-compatible alias.
CompilationError = CompileError


class DeployError(AgentKitError):
    """Raised when deployment to Agent Runtime fails."""


class PolicyError(AgentKitError):
    """Raised when policy compilation or enforcement fails."""


class RegistryError(AgentKitError):
    """Raised when Skill Registry or Agent Registry operations fail."""


class EvalError(AgentKitError):
    """Raised when evaluation execution or assertion fails."""
