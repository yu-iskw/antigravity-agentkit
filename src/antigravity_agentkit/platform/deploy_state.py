"""Deploy state persistence for rollback and status."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from antigravity_agentkit.exceptions import DeployError

DEPLOY_STATE_FILENAME = "deploy-state.json"
_MAX_HISTORY = 10
_MIN_DIGEST_PREFIX_LEN = 12


@dataclass
class DeployRecord:
    """Single deploy revision record."""

    resource_name: str
    package_digest: str
    git_sha: str | None
    deployed_at: str
    package_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resourceName": self.resource_name,
            "packageDigest": self.package_digest,
            "gitSha": self.git_sha,
            "deployedAt": self.deployed_at,
            "packageDir": self.package_dir,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeployRecord:
        return cls(
            resource_name=str(data["resourceName"]),
            package_digest=str(data.get("packageDigest", "")),
            git_sha=data.get("gitSha"),
            deployed_at=str(data.get("deployedAt", "")),
            package_dir=str(data.get("packageDir", "")),
        )


@dataclass
class DeployState:
    """Current deploy state with revision history."""

    resource_name: str
    package_digest: str
    git_sha: str | None
    deployed_at: str
    package_dir: str
    history: list[DeployRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resourceName": self.resource_name,
            "packageDigest": self.package_digest,
            "gitSha": self.git_sha,
            "deployedAt": self.deployed_at,
            "packageDir": self.package_dir,
            "history": [item.to_dict() for item in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeployState:
        history = [DeployRecord.from_dict(item) for item in data.get("history", [])]
        return cls(
            resource_name=str(data.get("resourceName", "")),
            package_digest=str(data.get("packageDigest", "")),
            git_sha=data.get("gitSha"),
            deployed_at=str(data.get("deployedAt", "")),
            package_dir=str(data.get("packageDir", "")),
            history=history,
        )


def deploy_storage_dir(package_dir: Path) -> Path:
    """Return the durable deploy metadata directory for a package."""
    return package_dir.parent / ".deploy" / package_dir.name


def deploy_state_path(package_dir: Path) -> Path:
    """Return durable deploy-state path outside the rebuilt package directory."""
    return deploy_storage_dir(package_dir) / DEPLOY_STATE_FILENAME


def revision_dir(package_dir: Path, package_digest: str) -> Path:
    """Return immutable package revision path for a digest."""
    digest_name = package_digest.removeprefix("sha256:")
    if not digest_name or any(char not in "0123456789abcdef" for char in digest_name.lower()):
        raise DeployError(f"Invalid package digest for revision storage: {package_digest!r}")
    return deploy_storage_dir(package_dir) / "revisions" / digest_name


def archive_package_revision(
    package_dir: Path,
    source_dir: Path,
    package_digest: str,
) -> Path:
    """Snapshot a source package into immutable digest-addressed storage."""
    destination = revision_dir(package_dir, package_digest)
    if destination.is_dir():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(source_dir, temporary)
    temporary.replace(destination)
    return destination


def load_deploy_state(package_dir: Path) -> DeployState | None:
    """Load deploy state when present."""
    path = deploy_state_path(package_dir)
    if not path.is_file():
        return None
    return DeployState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_deploy_state(package_dir: Path, state: DeployState) -> Path:
    """Persist deploy state JSON."""
    path = deploy_state_path(package_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    return path


def _prune_unreferenced_revisions(package_dir: Path, state: DeployState) -> None:
    revisions_root = deploy_storage_dir(package_dir) / "revisions"
    if not revisions_root.is_dir():
        return
    referenced = {state.package_dir, *(record.package_dir for record in state.history)}
    for candidate in revisions_root.iterdir():
        if candidate.is_dir() and str(candidate) not in referenced:
            shutil.rmtree(candidate)


def record_deploy(
    package_dir: Path,
    *,
    resource_name: str,
    package_digest: str,
    git_sha: str | None,
    deployed_package_dir: Path | None = None,
) -> DeployState:
    """Append deploy record and write deploy-state.json."""
    now = datetime.now(UTC).isoformat()
    history: list[DeployRecord] = []
    previous = load_deploy_state(package_dir)
    if previous is not None:
        history.append(
            DeployRecord(
                resource_name=previous.resource_name,
                package_digest=previous.package_digest,
                git_sha=previous.git_sha,
                deployed_at=previous.deployed_at,
                package_dir=previous.package_dir,
            )
        )
        history.extend(previous.history)
    history = history[:_MAX_HISTORY]

    state = DeployState(
        resource_name=resource_name,
        package_digest=package_digest,
        git_sha=git_sha,
        deployed_at=now,
        package_dir=str(deployed_package_dir or package_dir),
        history=history,
    )
    write_deploy_state(package_dir, state)
    _prune_unreferenced_revisions(package_dir, state)
    return state


def resolve_rollback_target(state: DeployState, target: str) -> DeployRecord:
    """Resolve rollback target by digest prefix, git SHA, or history index."""
    records = [DeployRecord.from_dict(state.to_dict()), *state.history]
    if target.isdigit():
        index = int(target)
        if index < 0 or index >= len(state.history):
            raise DeployError(f"History index out of range: {index}")
        return state.history[index]
    if target.startswith("sha256:"):
        for record in records:
            if record.package_digest.startswith(target) or record.package_digest == target:
                return record
    for record in records:
        if record.git_sha and (record.git_sha == target or record.git_sha.startswith(target)):
            return record
    normalized = target.lower()
    if len(normalized) >= _MIN_DIGEST_PREFIX_LEN and all(
        char in "0123456789abcdef" for char in normalized
    ):
        for record in records:
            digest_body = record.package_digest.removeprefix("sha256:")
            if digest_body.startswith(normalized) or record.package_digest == target:
                return record
    raise DeployError(f"No deploy record matches rollback target: {target!r}")
