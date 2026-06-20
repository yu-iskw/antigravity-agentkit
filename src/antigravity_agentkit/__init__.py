"""Antigravity AgentKit — declarative agent compiler and governance layer."""

from antigravity_agentkit.compiler import compile_agent_ir, compile_from_data
from antigravity_agentkit.deploy import build_deployment_config, build_source_package, deploy
from antigravity_agentkit.evals import EvalRunResult as EvalReport, run_evals
from antigravity_agentkit.ir import CompiledAgentIR
from antigravity_agentkit.ir_serde import ir_to_dict
from antigravity_agentkit.loader import load_agent_directory, load_deployment
from antigravity_agentkit.project import AgentProject
from antigravity_agentkit.registry import build_agent_registry_metadata, publish_skill
from antigravity_agentkit.runtime import RuntimeAgent
from antigravity_agentkit.schema.agent import AgentProjectData
from antigravity_agentkit.sdk.policies import compile_sdk_policies
from antigravity_agentkit.validator import validate_project

__all__ = [
    "AgentProject",
    "AgentProjectData",
    "CompiledAgentIR",
    "EvalReport",
    "RuntimeAgent",
    "build_agent_registry_metadata",
    "build_deployment_config",
    "build_source_package",
    "compile_agent_ir",
    "compile_from_data",
    "compile_sdk_policies",
    "deploy",
    "ir_to_dict",
    "load_agent",
    "load_agent_directory",
    "load_deployment",
    "publish_skill",
    "run_evals",
    "validate_project",
]


def load_agent(path: str) -> AgentProject:
    """Load an agent directory as an AgentProject."""
    return AgentProject.load(path)
