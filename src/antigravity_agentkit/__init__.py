"""Antigravity AgentKit — declarative agent compiler and governance layer."""

from antigravity_agentkit.compiler import compile_agent_config, compile_to_sdk_config
from antigravity_agentkit.deploy import build_deployment_config, build_source_package, deploy
from antigravity_agentkit.evals import run_evals
from antigravity_agentkit.loader import load_agent_directory
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.registry import build_agent_registry_metadata, publish_skill
from antigravity_agentkit.runtime import RuntimeAgent
from antigravity_agentkit.schema.agent import AgentProjectData, CompiledAgentConfig
from antigravity_agentkit.sdk import compile_sdk_policies
from antigravity_agentkit.validator import validate_project

__all__ = [
    "AgentProject",
    "AgentProjectData",
    "CompiledAgentConfig",
    "RuntimeAgent",
    "build_agent_registry_metadata",
    "build_deployment_config",
    "build_source_package",
    "compile_agent_config",
    "compile_sdk_policies",
    "compile_to_sdk_config",
    "deploy",
    "load_agent",
    "load_agent_directory",
    "publish_skill",
    "run_evals",
    "validate_project",
]


def load_agent(path: str) -> AgentProject:
    """Load an agent directory as an AgentProject."""
    return AgentProject.load(path)
