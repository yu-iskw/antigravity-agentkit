"""Skill Registry publish helpers."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from antigravity_agentkit.exceptions import RegistryError
from antigravity_agentkit.skills import SKILL_FILENAME, load_skill_directory, validate_skill_name

_MAX_SKILL_FILE_BYTES = 10 * 1024 * 1024


def _safe_zip_path(root: Path, file_path: Path) -> str:
    """Return a zip archive member path that rejects traversal."""
    rel = file_path.relative_to(root).as_posix()
    if rel.startswith("../") or "/../" in f"/{rel}/":
        raise RegistryError(f"Path traversal detected in skill package: {rel}")
    return rel


def _iter_skill_files(skill_root: Path) -> list[Path]:
    """Return sorted skill files after structural validation."""
    skill_path = skill_root / SKILL_FILENAME
    if not skill_path.is_file():
        raise RegistryError(f"Skill package missing {SKILL_FILENAME}: {skill_root}")

    files: list[Path] = []
    for path in skill_root.rglob("*"):
        if path.is_symlink():
            raise RegistryError(f"Symlinks are not allowed in skill packages: {path}")
        if not path.is_file():
            continue
        if path.stat().st_size > _MAX_SKILL_FILE_BYTES:
            raise RegistryError(f"Skill file exceeds size limit: {path}")
        files.append(path)
    return sorted(files)


def publish_skill(  # noqa: PLR0913
    skill_dir: str | Path,
    *,
    output_dir: str | Path | None = None,
    project: str | None = None,
    location: str | None = None,
    live: bool = False,
    write_lock: bool = False,
) -> dict[str, Any]:
    """Validate a skill package and create a zip archive; optionally upload live."""
    skill_root = Path(skill_dir).resolve()
    if not skill_root.is_dir():
        raise RegistryError(f"Skill directory not found: {skill_root}")

    out_dir = Path(output_dir or skill_root.parent / ".build" / "skills").resolve()
    if out_dir == skill_root or out_dir.is_relative_to(skill_root):
        raise RegistryError(f"Skill output directory cannot be inside the skill package: {out_dir}")

    skill = load_skill_directory(skill_root)
    validate_skill_name(skill.name)
    skill_files = _iter_skill_files(skill_root)

    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / f"{skill.name}.zip"

    hasher = hashlib.sha256()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in skill_files:
            member = _safe_zip_path(skill_root, file_path)
            payload = file_path.read_bytes()
            archive.writestr(member, payload)
            hasher.update(member.encode("utf-8"))
            hasher.update(payload)

    result = {
        "status": "packaged",
        "skillName": skill.name,
        "archivePath": str(archive_path),
        "sha256": hasher.hexdigest(),
        "project": project,
        "location": location,
        "registryRef": (
            f"projects/{project}/locations/{location}/skills/{skill.name}"
            if project and location
            else None
        ),
    }

    if live:
        if not project or not location:
            raise RegistryError("Live publish-skill requires --project and --location.")
        from antigravity_agentkit.platform.registry import publish_skill_live

        live_result = publish_skill_live(
            project_id=project,
            location=location,
            skill_name=skill.name,
            zip_path=archive_path,
            sha256=f"sha256:{hasher.hexdigest()}",
        )
        result.update(live_result)

    if write_lock:
        lock_path = skill_root.parent.parent / "skills.lock"
        lock_path.write_text(
            json.dumps({skill.name: result.get("registryRef", "")}, indent=2) + "\n",
            encoding="utf-8",
        )
        result["skillsLockPath"] = str(lock_path)

    return result
