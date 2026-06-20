"""Load agent directory contents into raw project data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from antigravity_agentkit.exceptions import LoadError
from antigravity_agentkit.schema.agent import AgentManifest, AgentProjectData
from antigravity_agentkit.schema.deployment import DeploymentManifest
from antigravity_agentkit.schema.evals import EvalSuite
from antigravity_agentkit.skills import discover_skills, load_skills
from antigravity_agentkit.subagents import discover_subagents, load_subagents_from_specs

AGENT_FILENAME = "agent.yaml"
DEPLOYMENT_FILENAME = "deployment.yaml"

TModel = TypeVar("TModel", bound=BaseModel)


def load_yaml_manifest(
    path: Path, model_type: type[TModel], label: str
) -> tuple[TModel, dict[str, Any]]:
    """Load and parse a YAML manifest file into a Pydantic model."""
    if not path.is_file():
        raise LoadError(f"{label} not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LoadError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise LoadError(f"{label} must be a YAML mapping: {path}")
    try:
        manifest = model_type.model_validate(raw)
    except Exception as exc:
        raise LoadError(f"Invalid {label} in {path}: {exc}") from exc
    return manifest, raw


def load_agent_yaml(path: Path) -> tuple[AgentManifest, dict[str, Any]]:
    """Load and parse agent.yaml."""
    return load_yaml_manifest(path, AgentManifest, "Agent manifest")


def load_deployment(root: str | Path) -> DeploymentManifest:
    """Load deployment.yaml from an agent directory."""
    agent_root = Path(root).resolve()
    manifest, _ = load_yaml_manifest(
        agent_root / DEPLOYMENT_FILENAME,
        DeploymentManifest,
        "Deployment manifest",
    )
    return manifest


def load_system_md(path: Path) -> str:
    """Load SYSTEM.md instructions."""
    if not path.is_file():
        raise LoadError(f"System instructions not found: {path}")
    return path.read_text(encoding="utf-8")


def _load_optional_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Load optional JSON file, returning None when missing."""
    if not path.is_file():
        return None, None
    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LoadError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LoadError(f"JSON file must be an object: {path}")
    return data, raw_text


def _load_optional_yaml(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Load optional YAML file, returning None when missing."""
    if not path.is_file():
        return None, None
    try:
        raw_text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise LoadError(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}, raw_text
    if not isinstance(data, dict):
        raise LoadError(f"YAML file must be a mapping: {path}")
    return data, raw_text


def _load_evals(root: Path, eval_files: list[str]) -> list[dict[str, Any]]:
    """Load evaluation suite files."""
    evals: list[dict[str, Any]] = []
    for rel_path in eval_files:
        path = (root / rel_path).resolve()
        data, _ = _load_optional_yaml(path)
        if data is None:
            raise LoadError(f"Eval file not found: {path}")
        suite = EvalSuite.from_dict(data)
        evals.append({"path": str(path), "suite": suite.model_dump(), "raw": data})
    return evals


def _load_skills(root: Path, manifest: AgentManifest) -> dict[str, Any]:
    """Load skills from manifest references or skills/ discovery."""
    skills_spec = manifest.spec.skills
    if skills_spec and skills_spec.local:
        loaded = load_skills(root, skills_spec.local)
    else:
        loaded = discover_skills(root)
    return dict(loaded)


def _load_subagents(root: Path, manifest: AgentManifest) -> dict[str, Any]:
    """Load subagents from manifest references or subagents/ discovery."""
    if manifest.spec.subagents:
        loaded = load_subagents_from_specs(root, manifest.spec.subagents)
    else:
        loaded = discover_subagents(root)
    return dict(loaded)


def load_agent_directory(path: str | Path) -> AgentProjectData:
    """Load an agent directory into raw project data.

    Required:
      - agent.yaml
      - SYSTEM.md (or path referenced by manifest)

    Optional (loaded when present or referenced):
      - mcp.json
      - policies.yaml
      - skills/
      - subagents/
      - evals/
    """
    root = Path(path).resolve()
    if not root.is_dir():
        raise LoadError(f"Agent directory not found: {root}")

    manifest, manifest_raw = load_agent_yaml(root / AGENT_FILENAME)
    system_path = root / manifest.spec.instructions.system
    system_instructions = load_system_md(system_path)

    mcp_config: dict[str, Any] | None = None
    mcp_raw: str | None = None
    if manifest.spec.mcp:
        mcp_path = root / manifest.spec.mcp.file
        mcp_config, mcp_raw = _load_optional_json(mcp_path)

    policies: dict[str, Any] | None = None
    policies_raw: str | None = None
    if manifest.spec.policies:
        policies_path = root / manifest.spec.policies.file
        policies, policies_raw = _load_optional_yaml(policies_path)

    skills = _load_skills(root, manifest)
    subagents = _load_subagents(root, manifest)

    evals: list[dict[str, Any]] = []
    if manifest.spec.evals and manifest.spec.evals.files:
        evals = _load_evals(root, manifest.spec.evals.files)

    return AgentProjectData(
        root=root,
        manifest=manifest,
        manifest_raw=manifest_raw,
        system_instructions=system_instructions,
        mcp_config=mcp_config,
        mcp_raw=mcp_raw,
        policies=policies,
        policies_raw=policies_raw,
        skills=skills,
        subagents=subagents,
        evals=evals,
    )
