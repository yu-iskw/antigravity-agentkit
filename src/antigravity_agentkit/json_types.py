"""JSON-compatible value types for compiled agent IR."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | Mapping[str, "JsonValue"] | Sequence["JsonValue"]
