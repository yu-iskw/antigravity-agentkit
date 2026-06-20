"""Ship agents to Google Cloud and other deployment targets."""

from __future__ import annotations

from antigravity_agentkit.deploy.agent_platform import (
    build_deployment_config,
    deploy,
)
from antigravity_agentkit.deploy.package import build_source_package
from antigravity_agentkit.loader import DEPLOYMENT_FILENAME, load_deployment

__all__ = [
    "DEPLOYMENT_FILENAME",
    "build_deployment_config",
    "build_source_package",
    "deploy",
    "load_deployment",
]
