"""Tests for Agent Registry and MCP registry metadata."""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from antigravity_agentkit.compiler import compile_agent_ir
from antigravity_agentkit.exceptions import RegistryError
from antigravity_agentkit.loader import load_deployment
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.registry import (
    PROVENANCE_ENV_GIT_SHA,
    PROVENANCE_ENV_PACKAGE_DIGEST,
    build_agent_registry_metadata,
    build_mcp_server_metadata,
    provenance_fields,
    publish_skill,
)
from antigravity_agentkit.registry.metadata import build_registry_metadata
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.tests.constants import TEST_GCP_LOCATION, TEST_GCP_PROJECT


def test_build_registry_metadata_preserves_frozen_labels(
    repo_root: Path,
) -> None:
    """Deep-frozen IR metadata labels survive registry metadata emission."""
    agent_dir = repo_root / "examples" / "agent_platform"
    deployment = load_deployment(agent_dir)
    ir = compile_agent_ir(agent_dir)

    metadata = build_registry_metadata(
        ir,
        deployment,
        target_name="agent-platform-runtime",
        location=TEST_GCP_LOCATION,
    )

    agent = metadata["agent"]
    assert isinstance(agent, dict)
    assert agent["labels"] == {
        "domain": "examples",
        "tier": "ship-demo",
    }
    json.dumps(metadata)


def test_build_stdio_mcp_server_metadata(mcp_agent_dir: Path) -> None:
    """Stdio registry metadata contains only stdio connection fields."""
    project = AgentProject.load(mcp_agent_dir)

    metadata = build_mcp_server_metadata(project)[0]

    assert metadata["transport"] == "stdio"
    assert metadata["command"] == "python3"
    assert metadata["args"] == ["server/clock_mcp.py"]
    assert "url" not in metadata
    assert "headerKeys" not in metadata


def test_build_http_mcp_server_metadata_excludes_header_values(
    hello_world_agent_dir: Path,
) -> None:
    """HTTP registry metadata exposes header names without secret values."""
    project = AgentProject.load(hello_world_agent_dir)
    project.data.mcp_config = {
        "mcpServers": {
            "remote": {
                "url": "https://example.com/mcp",
                "headers": {
                    "Authorization": "Bearer ${TOKEN}",
                    "X-Trace-Id": "private-trace-value",
                },
            }
        }
    }

    metadata = build_mcp_server_metadata(project)[0]

    assert metadata["transport"] == "http"
    assert metadata["url"] == "https://example.com/mcp"
    assert metadata["headerKeys"] == ["Authorization", "X-Trace-Id"]
    assert "command" not in metadata
    assert "args" not in metadata
    assert "envKeys" not in metadata
    serialized = json.dumps(metadata)
    assert "Bearer ${TOKEN}" not in serialized
    assert "private-trace-value" not in serialized


def test_provenance_fields_maps_optional_inputs() -> None:
    """Provenance helper maps CI inputs to metadata keys."""
    assert not provenance_fields()
    assert provenance_fields(git_sha="abc", package_digest="def") == {
        "gitSha": "abc",
        "packageDigest": "def",
    }


def test_build_agent_registry_metadata_from_ship_fixture(
    ship_context: tuple[AgentProject, DeploymentManifest],
) -> None:
    """Register metadata includes deployment fields and optional CI provenance."""
    project, deployment = ship_context
    env = {
        PROVENANCE_ENV_GIT_SHA: "abc123",
        PROVENANCE_ENV_PACKAGE_DIGEST: "deadbeef",
    }
    with patch.dict(os.environ, env, clear=False):
        metadata = build_agent_registry_metadata(
            project,
            deployment,
            location=TEST_GCP_LOCATION,
        )

    assert metadata["agent"]["name"] == "ship-agent"
    assert metadata["target"]["name"] == "agent-platform-runtime"
    assert metadata["identity"]["serviceAccount"] == deployment.spec.service_account
    assert "generatedAt" in metadata
    assert metadata["gitSha"] == "abc123"
    assert metadata["packageDigest"] == "deadbeef"


def test_publish_skill_packages_greeting_helper(skills_agent_dir: Path, tmp_path: Path) -> None:
    """publish_skill validates and zips a local skill package."""
    skill_dir = skills_agent_dir / "skills" / "greeting-helper"
    result = publish_skill(
        skill_dir,
        output_dir=tmp_path,
        project=TEST_GCP_PROJECT,
        location=TEST_GCP_LOCATION,
    )

    assert result["status"] == "packaged"
    assert result["skillName"] == "greeting-helper"
    archive = Path(result["archivePath"])
    assert archive.is_file()
    assert result["sha256"]
    assert (
        result["registryRef"]
        == f"projects/{TEST_GCP_PROJECT}/locations/{TEST_GCP_LOCATION}/skills/greeting-helper"
    )


def test_publish_skill_rejects_output_inside_package(skills_agent_dir: Path) -> None:
    """Skill archives cannot be written beneath the source package."""
    skill_dir = skills_agent_dir / "skills" / "greeting-helper"

    with pytest.raises(RegistryError, match="cannot be inside"):
        publish_skill(skill_dir, output_dir=skill_dir / "out")


def test_publish_skill_repeat_is_stable(skills_agent_dir: Path, tmp_path: Path) -> None:
    """Repeated external publishing does not include a previous archive."""
    skill_dir = skills_agent_dir / "skills" / "greeting-helper"

    first = publish_skill(skill_dir, output_dir=tmp_path)
    second = publish_skill(skill_dir, output_dir=tmp_path)

    assert first["sha256"] == second["sha256"]
    with zipfile.ZipFile(second["archivePath"]) as archive:
        assert sorted(archive.namelist()) == sorted(["SKILL.md", "scripts/greet.sh"])


def test_publish_skill_write_lock_requires_live(
    skills_agent_dir: Path,
    tmp_path: Path,
) -> None:
    """Local packaging cannot create a purported immutable registry pin."""
    skill_dir = skills_agent_dir / "skills" / "greeting-helper"

    with pytest.raises(RegistryError, match="requires --live"):
        publish_skill(skill_dir, output_dir=tmp_path, write_lock=True)


def test_publish_skill_merges_live_revision_locks(
    skills_agent_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live lock writes preserve other skills and pin immutable revisions."""
    agent_root = tmp_path / "agent"
    shutil.copytree(skills_agent_dir, agent_root)
    second_skill = agent_root / "skills" / "farewell-helper"
    second_skill.mkdir()
    (second_skill / "SKILL.md").write_text(
        "---\nname: farewell-helper\ndescription: Say goodbye.\nlicense: Apache-2.0\n---\n\n# Farewell\n",
        encoding="utf-8",
    )

    publish_counts: dict[str, int] = {}

    def fake_publish_skill_live(**kwargs: object) -> dict[str, object]:
        skill_name = str(kwargs["skill_name"])
        publish_counts[skill_name] = publish_counts.get(skill_name, 0) + 1
        registry_name = (
            f"projects/{TEST_GCP_PROJECT}/locations/{TEST_GCP_LOCATION}/skills/{skill_name}"
        )
        return {
            "status": "published",
            "registryRef": registry_name,
            "revision": f"{registry_name}/revisions/rev-{publish_counts[skill_name]}",
            "sha256": kwargs["sha256"],
        }

    monkeypatch.setattr(
        "antigravity_agentkit.platform.registry.publish_skill_live",
        fake_publish_skill_live,
    )
    for skill_name in ("greeting-helper", "farewell-helper"):
        publish_skill(
            agent_root / "skills" / skill_name,
            output_dir=tmp_path / "archives",
            project=TEST_GCP_PROJECT,
            location=TEST_GCP_LOCATION,
            live=True,
            write_lock=True,
        )
    publish_skill(
        agent_root / "skills" / "greeting-helper",
        output_dir=tmp_path / "archives",
        project=TEST_GCP_PROJECT,
        location=TEST_GCP_LOCATION,
        live=True,
        write_lock=True,
    )

    lock = yaml.safe_load((agent_root / "skills.lock").read_text(encoding="utf-8"))
    assert lock["version"] == 1
    assert [entry["name"] for entry in lock["skills"]] == [
        "farewell-helper",
        "greeting-helper",
    ]
    revisions = {entry["name"]: entry["revision"] for entry in lock["skills"]}
    assert revisions["farewell-helper"].endswith("/revisions/rev-1")
    assert revisions["greeting-helper"].endswith("/revisions/rev-2")
    assert all(entry["sha256"].startswith("sha256:") for entry in lock["skills"])


def test_publish_skill_does_not_overwrite_malformed_lock(
    skills_agent_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed existing lock data is preserved for manual recovery."""
    agent_root = tmp_path / "agent"
    shutil.copytree(skills_agent_dir, agent_root)
    lock_path = agent_root / "skills.lock"
    original = "version: 2\nskills: []\n"
    lock_path.write_text(original, encoding="utf-8")
    registry_name = (
        f"projects/{TEST_GCP_PROJECT}/locations/{TEST_GCP_LOCATION}/skills/greeting-helper"
    )
    monkeypatch.setattr(
        "antigravity_agentkit.platform.registry.publish_skill_live",
        lambda **kwargs: {
            "status": "published",
            "registryRef": registry_name,
            "revision": f"{registry_name}/revisions/rev-1",
            "sha256": kwargs["sha256"],
        },
    )

    with pytest.raises(RegistryError, match="version: 1"):
        publish_skill(
            agent_root / "skills" / "greeting-helper",
            output_dir=tmp_path / "archives",
            project=TEST_GCP_PROJECT,
            location=TEST_GCP_LOCATION,
            live=True,
            write_lock=True,
        )

    assert lock_path.read_text(encoding="utf-8") == original
