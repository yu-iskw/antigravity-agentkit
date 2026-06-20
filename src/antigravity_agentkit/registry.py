"""Agent Registry and Skill Registry metadata builders."""

from __future__ import annotations

import hashlib
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from antigravity_agentkit.compiler import compile_tool_metadata
from antigravity_agentkit.exceptions import RegistryError
from antigravity_agentkit.mcp import parse_mcp_dict
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.skills import SKILL_FILENAME, load_skill_directory, validate_skill_name
from antigravity_agentkit.subagents import compile_subagent_ir

_MAX_SKILL_FILE_BYTES = 10 * 1024 * 1024
PROVENANCE_ENV_GIT_SHA = "AGK_GIT_SHA"
PROVENANCE_ENV_PACKAGE_DIGEST = "AGK_PACKAGE_DIGEST"


def provenance_fields(
    git_sha: str | None = None,
    package_digest: str | None = None,
) -> dict[str, str]:
    """Map optional CI inputs to registry metadata provenance keys."""
    provenance: dict[str, str] = {}
    if git_sha:
        provenance["gitSha"] = git_sha
    if package_digest:
        provenance["packageDigest"] = package_digest
    return provenance


def _provenance_from_env() -> dict[str, str]:
    return provenance_fields(
        os.environ.get(PROVENANCE_ENV_GIT_SHA),
        os.environ.get(PROVENANCE_ENV_PACKAGE_DIGEST),
    )


def build_agent_registry_metadata(
    project: AgentProject,
    deployment: DeploymentManifest,
) -> dict[str, Any]:
    """Build Agent Registry metadata from a loaded project and deployment."""
    manifest = project.manifest
    data = project.data
    deploy_spec = deployment.spec
    vertex = manifest.spec.runtime.vertex

    mcp_servers: list[str] = []
    if data.mcp_config:
        mcp_servers = sorted(parse_mcp_dict(data.mcp_config).mcp_servers.keys())

    subagent_ir = compile_subagent_ir(data.subagents)
    enable_subagents = data.manifest.spec.runtime.capabilities.enable_subagents
    if enable_subagents is None:
        enable_subagents = bool(subagent_ir)

    tools = [
        str(tool["name"])
        for tool in compile_tool_metadata(
            data,
            subagent_ir,
            enable_subagents=enable_subagents,
        )
        if isinstance(tool, dict) and "name" in tool
    ]

    skills: list[str] = sorted(data.skills.keys())
    subagents = sorted(data.subagents.keys())

    metadata: dict[str, Any] = {
        "name": manifest.metadata.name,
        "displayName": manifest.metadata.display_name or manifest.metadata.name,
        "description": manifest.metadata.description,
        "owner": manifest.metadata.owner,
        "labels": dict(manifest.metadata.labels),
        "runtime": {
            "framework": manifest.spec.runtime.framework,
            "vertexEnabled": vertex.enabled,
            "project": vertex.project,
            "location": vertex.location,
        },
        "deployment": {
            "target": deploy_spec.target,
            "serviceAccount": deploy_spec.service_account,
            "labels": dict(deploy_spec.labels),
        },
        "mcpServers": mcp_servers,
        "tools": tools,
        "skills": skills,
        "subagents": subagents,
        "policyFile": manifest.spec.policies.file if manifest.spec.policies else None,
        "sourceRoot": str(project.root),
        "generatedAt": datetime.now(UTC).isoformat(),
    }
    metadata.update(_provenance_from_env())
    return metadata


def build_mcp_server_metadata(
    project: AgentProject,
) -> list[dict[str, Any]]:
    """Build MCP server registry metadata for servers declared in the project."""
    data = project.data
    if not data.mcp_config:
        return []

    config = parse_mcp_dict(data.mcp_config)
    servers: list[dict[str, Any]] = []
    for name, server in config.mcp_servers.items():
        metadata: dict[str, Any] = {
            "name": name,
            "owner": project.manifest.metadata.owner,
            "agentName": project.manifest.metadata.name,
        }
        if server.url:
            metadata.update(
                {
                    "transport": "http",
                    "url": server.url,
                    "headerKeys": sorted(server.headers),
                }
            )
        else:
            metadata.update(
                {
                    "transport": "stdio",
                    "command": server.command,
                    "args": list(server.args),
                    "envKeys": sorted(server.env),
                }
            )
        servers.append(metadata)
    return servers


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


def publish_skill(
    skill_dir: str | Path,
    *,
    output_dir: str | Path | None = None,
    project: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    """Validate a skill package and create a zip archive (local publish stub)."""
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

    return {
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
