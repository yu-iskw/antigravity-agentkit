"""Skill Registry publish helpers."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any

import yaml

from antigravity_agentkit.exceptions import RegistryError
from antigravity_agentkit.skills import SKILL_FILENAME, load_skill_directory, validate_skill_name

_MAX_SKILL_FILE_BYTES = 10 * 1024 * 1024
_SKILLS_LOCK_FILENAME = "skills.lock"


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


def _find_agent_root(skill_root: Path) -> Path:
    for candidate in skill_root.parents:
        if (candidate / "agent.yaml").is_file():
            return candidate
    raise RegistryError(
        f"Cannot write {_SKILLS_LOCK_FILENAME}: no parent agent.yaml found for {skill_root}"
    )


def _load_skills_lock(lock_path: Path) -> list[dict[str, Any]]:
    if not lock_path.is_file():
        return []
    try:
        payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RegistryError(f"Invalid {_SKILLS_LOCK_FILENAME}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise RegistryError(f"{_SKILLS_LOCK_FILENAME} must contain version: 1")
    skills = payload.get("skills")
    if not isinstance(skills, list) or any(not isinstance(item, dict) for item in skills):
        raise RegistryError(f"{_SKILLS_LOCK_FILENAME} skills must be a list of mappings")
    names = [item.get("name") for item in skills]
    if any(not isinstance(name, str) or not name for name in names) or len(names) != len(
        set(names)
    ):
        raise RegistryError(f"{_SKILLS_LOCK_FILENAME} skill names must be non-empty and unique")
    return skills


def _read_skills_lock(skill_root: Path) -> tuple[Path, list[dict[str, Any]]]:
    agent_root = _find_agent_root(skill_root)
    lock_path = agent_root / _SKILLS_LOCK_FILENAME
    return lock_path, _load_skills_lock(lock_path)


def _write_skill_lock(
    skill_root: Path,
    *,
    skill_name: str,
    registry_name: str,
    revision: str,
    sha256: str,
) -> Path:
    lock_path, skills = _read_skills_lock(skill_root)
    entry = {
        "name": skill_name,
        "source": "local",
        "registryName": registry_name,
        "revision": revision,
        "sha256": sha256,
    }
    merged = [item for item in skills if item["name"] != skill_name]
    merged.append(entry)
    merged.sort(key=lambda item: str(item["name"]))
    temporary = lock_path.with_name(f".{lock_path.name}.tmp")
    temporary.write_text(
        yaml.safe_dump({"version": 1, "skills": merged}, sort_keys=False),
        encoding="utf-8",
    )
    temporary.replace(lock_path)
    return lock_path


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
    if write_lock and not live:
        raise RegistryError("--write-lock requires --live to pin an immutable revision.")

    out_dir = Path(output_dir or skill_root.parent / ".build" / "skills").resolve()
    if out_dir == skill_root or out_dir.is_relative_to(skill_root):
        raise RegistryError(f"Skill output directory cannot be inside the skill package: {out_dir}")

    if write_lock:
        _read_skills_lock(skill_root)

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
        "sha256": f"sha256:{hasher.hexdigest()}",
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
        registry_name = str(result.get("registryRef") or "")
        revision = str(result.get("revision") or "")
        if not registry_name or not revision:
            raise RegistryError("Skill Registry did not return a registry name and revision.")
        lock_path = _write_skill_lock(
            skill_root,
            skill_name=skill.name,
            registry_name=registry_name,
            revision=revision,
            sha256=str(result["sha256"]),
        )
        result["skillsLockPath"] = str(lock_path)

    return result
