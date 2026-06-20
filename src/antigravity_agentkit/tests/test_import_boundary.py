"""Import boundary tests for RFC 0002 core isolation."""

from __future__ import annotations

import ast
from pathlib import Path

_CORE_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN_PREFIXES = (
    "google.antigravity",
    "google.cloud",
    "antigravity_agentkit.sdk",
    "antigravity_agentkit.deploy",
)
_STRICT_CORE_MODULES = (
    "compiler.py",
    "loader.py",
    "validator.py",
    "ir.py",
    "ir_serde.py",
    "json_types.py",
    "evals.py",
)


def _top_level_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def test_strict_core_modules_do_not_import_forbidden_packages() -> None:
    """Strict core modules must not import SDK, GCP, or deploy adapters at load time."""
    violations: list[str] = []
    for relative in _STRICT_CORE_MODULES:
        module_path = _CORE_ROOT / relative
        for imported in _top_level_imports(module_path):
            if any(imported.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES):
                violations.append(f"{relative}: {imported}")
    assert not violations, "Forbidden imports in core:\n" + "\n".join(violations)


def test_project_does_not_import_sdk_at_module_level() -> None:
    """AgentProject must lazy-import SDK runtime only inside create_agent()."""
    imports = _top_level_imports(_CORE_ROOT / "project.py")
    forbidden = [item for item in imports if item.startswith(_FORBIDDEN_PREFIXES)]
    assert not forbidden
