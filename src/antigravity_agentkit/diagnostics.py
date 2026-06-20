"""Rich validation diagnostics for AgentKit."""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, Field


class DiagnosticLevel(str, Enum):
    """Severity level for a validation diagnostic."""

    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


class Diagnostic(BaseModel):
    """A single validation or compilation diagnostic."""

    level: DiagnosticLevel
    code: str = Field(
        ...,
        description="Stable diagnostic code, e.g. AGK-MCP-003 or AGK-SKILL-001.",
        pattern=r"^AGK-[A-Z]+-\d{3}$",
    )
    message: str
    file: str | None = None
    path: str | None = Field(
        default=None,
        description="JSON Pointer or path within the source file.",
    )
    hint: str | None = None

    def format(self) -> str:
        """Format this diagnostic as a single human-readable line."""
        location = f"  file: {self.file}\n" if self.file else ""
        json_path = f"  path: {self.path}\n" if self.path else ""
        hint_line = f"  hint: {self.hint}" if self.hint else ""
        body = location + json_path + hint_line
        suffix = f"\n{body}" if body else ""
        return f"{self.level.value} {self.code}: {self.message}{suffix}"


class DiagnosticCollector:
    """Collects diagnostics during validation and compilation."""

    def __init__(self) -> None:
        self._diagnostics: list[Diagnostic] = []

    @property
    def diagnostics(self) -> list[Diagnostic]:
        """Return a copy of collected diagnostics."""
        return list(self._diagnostics)

    def add(self, diagnostic: Diagnostic) -> None:
        """Add a diagnostic to the collector."""
        self._diagnostics.append(diagnostic)

    def add_error(
        self,
        code: str,
        message: str,
        *,
        file: str | None = None,
        path: str | None = None,
        hint: str | None = None,
    ) -> None:
        """Record an ERROR-level diagnostic."""
        self.add(
            Diagnostic(
                level=DiagnosticLevel.ERROR,
                code=code,
                message=message,
                file=file,
                path=path,
                hint=hint,
            )
        )

    def add_warn(
        self,
        code: str,
        message: str,
        *,
        file: str | None = None,
        path: str | None = None,
        hint: str | None = None,
    ) -> None:
        """Record a WARN-level diagnostic."""
        self.add(
            Diagnostic(
                level=DiagnosticLevel.WARN,
                code=code,
                message=message,
                file=file,
                path=path,
                hint=hint,
            )
        )

    def add_info(
        self,
        code: str,
        message: str,
        *,
        file: str | None = None,
        path: str | None = None,
        hint: str | None = None,
    ) -> None:
        """Record an INFO-level diagnostic."""
        self.add(
            Diagnostic(
                level=DiagnosticLevel.INFO,
                code=code,
                message=message,
                file=file,
                path=path,
                hint=hint,
            )
        )

    def extend(self, other: DiagnosticCollector) -> None:
        """Merge diagnostics from another collector."""
        self._diagnostics.extend(other.diagnostics)

    def has_errors(self) -> bool:
        """Return True if any ERROR-level diagnostics were recorded."""
        return any(d.level == DiagnosticLevel.ERROR for d in self._diagnostics)

    def errors(self) -> list[Diagnostic]:
        """Return all ERROR-level diagnostics."""
        return [d for d in self._diagnostics if d.level == DiagnosticLevel.ERROR]

    def warnings(self) -> list[Diagnostic]:
        """Return all WARN-level diagnostics."""
        return [d for d in self._diagnostics if d.level == DiagnosticLevel.WARN]

    def format_all(self) -> str:
        """Format all diagnostics as a multi-line string."""
        return "\n\n".join(d.format() for d in self._diagnostics)

    def clear(self) -> Self:
        """Clear all collected diagnostics and return self."""
        self._diagnostics.clear()
        return self
