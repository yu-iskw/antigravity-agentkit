"""SDK compatibility negotiation."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import inspect
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class SdkCapabilities:
    """Compatibility report for the installed google-antigravity SDK."""

    sdk_version: str | None
    local_agent_config_params: frozenset[str]
    local_agent_config_accepts_kwargs: bool
    accepts_model: bool
    accepts_vertex: bool
    accepts_project: bool
    accepts_location: bool
    accepts_mcp_servers: bool
    accepts_tools: bool
    accepts_policies: bool
    accepts_capabilities: bool
    accepts_skills_paths: bool
    accepts_subagents: bool
    has_capabilities_config: bool
    has_mcp_stdio_server: bool
    has_mcp_sse_server: bool
    has_mcp_streamable_http_server: bool
    has_subagent_config: bool
    policy_module_path: str | None

    @classmethod
    def unsupported(cls, *, sdk_version: str | None = None) -> SdkCapabilities:
        return cls(
            sdk_version=sdk_version,
            local_agent_config_params=frozenset(),
            local_agent_config_accepts_kwargs=False,
            accepts_model=False,
            accepts_vertex=False,
            accepts_project=False,
            accepts_location=False,
            accepts_mcp_servers=False,
            accepts_tools=False,
            accepts_policies=False,
            accepts_capabilities=False,
            accepts_skills_paths=False,
            accepts_subagents=False,
            has_capabilities_config=False,
            has_mcp_stdio_server=False,
            has_mcp_sse_server=False,
            has_mcp_streamable_http_server=False,
            has_subagent_config=False,
            policy_module_path=None,
        )

    @classmethod
    def detect(cls) -> SdkCapabilities:
        """Detect installed SDK capabilities (cached per process)."""
        return _detect_sdk_capabilities()


@lru_cache(maxsize=1)
def _detect_sdk_capabilities() -> SdkCapabilities:
    sdk_version: str | None = None
    try:
        sdk_version = importlib.metadata.version("google-antigravity")
    except importlib.metadata.PackageNotFoundError:
        return SdkCapabilities.unsupported()

    try:
        from google.antigravity import LocalAgentConfig, types as sdk_types
    except ImportError:
        return SdkCapabilities.unsupported(sdk_version=sdk_version)

    signature = inspect.signature(LocalAgentConfig)
    params = frozenset(signature.parameters)
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )

    policy_module_path: str | None = None
    if importlib.util.find_spec("google.antigravity.policy") is not None:
        policy_module_path = "google.antigravity.policy"
    elif importlib.util.find_spec("google.antigravity.hooks.policy") is not None:
        policy_module_path = "google.antigravity.hooks.policy"

    def accepts(name: str) -> bool:
        return name in params or accepts_kwargs

    return SdkCapabilities(
        sdk_version=sdk_version,
        local_agent_config_params=params,
        local_agent_config_accepts_kwargs=accepts_kwargs,
        accepts_model=accepts("model"),
        accepts_vertex=accepts("vertex"),
        accepts_project=accepts("project"),
        accepts_location=accepts("location"),
        accepts_mcp_servers=accepts("mcp_servers"),
        accepts_tools=accepts("tools"),
        accepts_policies=accepts("policies"),
        accepts_capabilities=accepts("capabilities"),
        accepts_skills_paths=accepts("skills_paths"),
        accepts_subagents=accepts("subagents"),
        has_capabilities_config=getattr(sdk_types, "CapabilitiesConfig", None) is not None,
        has_mcp_stdio_server=getattr(sdk_types, "McpStdioServer", None) is not None,
        has_mcp_sse_server=getattr(sdk_types, "McpSseServer", None) is not None,
        has_mcp_streamable_http_server=getattr(sdk_types, "McpStreamableHttpServer", None)
        is not None,
        has_subagent_config=getattr(sdk_types, "SubagentConfig", None) is not None,
        policy_module_path=policy_module_path,
    )
