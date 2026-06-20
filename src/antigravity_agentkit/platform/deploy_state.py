"""Deploy state persistence for rollback and status."""

from __future__ import annotations

import json
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


def deploy_state_path(package_dir: Path) -> Path:
    """Return path to deploy-state.json inside a package directory."""
    return package_dir / DEPLOY_STATE_FILENAME


def load_deploy_state(package_dir: Path) -> DeployState | None:
    """Load deploy state when present."""
    path = deploy_state_path(package_dir)
    if not path.is_file():
        return None
    return DeployState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_deploy_state(package_dir: Path, state: DeployState) -> Path:
    """Persist deploy state JSON."""
    path = deploy_state_path(package_dir)
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    return path


def record_deploy(
    package_dir: Path,
    *,
    resource_name: str,
    package_digest: str,
    git_sha: str | None,
    previous: DeployState | None = None,
) -> DeployState:
    """Append deploy record and write deploy-state.json."""
    now = datetime.now(UTC).isoformat()
    history: list[DeployRecord] = []
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
        package_dir=str(package_dir),
        history=history,
    )
    write_deploy_state(package_dir, state)
    return state


def resolve_rollback_target(state: DeployState, target: str) -> DeployRecord:
    """Resolve rollback target by digest prefix, git SHA, or history index."""
    if target.startswith("sha256:") or len(target) >= _MIN_DIGEST_PREFIX_LEN:
        for record in [DeployRecord.from_dict(state.to_dict()), *state.history]:
            if record.package_digest.startswith(target) or record.package_digest == target:
                return record
    if target.isdigit():
        index = int(target)
        if index < 0 or index >= len(state.history):
            raise DeployError(f"History index out of range: {index}")
        return state.history[index]
    for record in [DeployRecord.from_dict(state.to_dict()), *state.history]:
        if record.git_sha and (record.git_sha == target or record.git_sha.startswith(target)):
            return record
    raise DeployError(f"No deploy record matches rollback target: {target!r}")
