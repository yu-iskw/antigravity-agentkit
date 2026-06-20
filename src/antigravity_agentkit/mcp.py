"""MCP configuration parser and compiler."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from antigravity_agentkit.exceptions import (
    CompilationError,
    LoadError,
    SecurityValidationError,
    ValidationError,
)
from antigravity_agentkit.ir import McpServerIR
from antigravity_agentkit.schema.mcp import McpConfig, McpServerConfig

SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|secret|token|password|credential|private[_-]?key)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"^sk_(live|test)_[A-Za-z0-9]+$"),
    re.compile(r"^AKIA[0-9A-Z]{16}$"),
    re.compile(r"^-----BEGIN .*PRIVATE KEY-----"),
    re.compile(r"^ghp_[A-Za-z0-9]{20,}$"),
    re.compile(r"^glpat-[A-Za-z0-9\-_]{20,}$"),
)
VERSION_PIN_PATTERN = re.compile(r"@[0-9]+\.[0-9]+")


def parse_mcp_dict(data: dict[str, Any]) -> McpConfig:
    """Parse mcp.json content from a dictionary."""
    try:
        return McpConfig.from_dict(data)
    except PydanticValidationError as exc:
        raise ValidationError(f"Invalid MCP configuration: {exc}") from exc


def parse_mcp_json(path: Path) -> McpConfig:
    """Parse mcp.json from disk."""
    if not path.is_file():
        raise LoadError(f"MCP config not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LoadError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise LoadError(f"MCP config must be a JSON object: {path}")
    return parse_mcp_dict(raw)


def _looks_like_secret(key: str, value: str) -> bool:
    """Return True when an env value appears to contain a secret."""
    if SECRET_KEY_PATTERN.search(key) and value and not value.startswith("${"):
        return True
    return any(pattern.match(value) for pattern in SECRET_VALUE_PATTERNS)


def _has_pinned_npx_package(args: list[str]) -> bool:
    """Return True when npx args include a version-pinned package."""
    for arg in args:
        if arg.startswith("-"):
            continue
        if "@" in arg and VERSION_PIN_PATTERN.search(arg):
            return True
    return False


def _validate_stdio_server_security(
    name: str,
    server: McpServerConfig,
    *,
    production: bool,
) -> list[str]:
    errors: list[str] = []
    command = server.command or ""
    args = server.args

    if command in {"sh", "bash", "zsh"} and "-c" in args:
        errors.append(f"MCP server '{name}': shell -c execution is not allowed")

    full_command = " ".join([command, *args])
    if "sh -c" in full_command or "bash -c" in full_command:
        errors.append(f"MCP server '{name}': shell -c execution is not allowed")

    if command == "npx" and "-y" in args and not _has_pinned_npx_package(args):
        errors.append(f"MCP server '{name}': unpinned npx -y package; pin version (e.g. pkg@1.2.3)")

    for key, value in server.env.items():
        if _looks_like_secret(key, value):
            errors.append(f"MCP server '{name}': env.{key} appears to contain an inline secret")

    if production and command in {"curl", "wget"}:
        errors.append(f"MCP server '{name}': command '{command}' is not allowed in production")

    return errors


def _validate_http_server_security(name: str, server: McpServerConfig) -> list[str]:
    errors: list[str] = []
    for key, value in server.headers.items():
        if _looks_like_secret(key, value):
            errors.append(f"MCP server '{name}': headers.{key} appears to contain an inline secret")
    return errors


def _validate_server_security(
    name: str,
    server: McpServerConfig,
    *,
    production: bool,
) -> list[str]:
    if server.url:
        return _validate_http_server_security(name, server)
    return _validate_stdio_server_security(name, server, production=production)


def validate_mcp_security(
    mcp_config: McpConfig | dict[str, Any],
    *,
    production: bool = False,
) -> list[str]:
    """Validate MCP configuration against security rules.

    Rejects shell -c invocations, inline secrets, and unpinned npx -y usage.
    """
    config = mcp_config if isinstance(mcp_config, McpConfig) else parse_mcp_dict(mcp_config)
    errors: list[str] = []

    for name, server in config.mcp_servers.items():
        errors.extend(_validate_server_security(name, server, production=production))

    return errors


def assert_mcp_security(
    mcp_config: McpConfig | dict[str, Any],
    *,
    production: bool = False,
) -> None:
    """Raise SecurityValidationError when MCP security validation fails."""
    errors = validate_mcp_security(mcp_config, production=production)
    if errors:
        raise SecurityValidationError("; ".join(errors))


def _append_tool_filters(result: dict[str, Any], server: McpServerConfig) -> None:
    if server.enabled_tools:
        result["enabledTools"] = list(server.enabled_tools)
    if server.disabled_tools:
        result["disabledTools"] = list(server.disabled_tools)


def compile_mcp_server_dict(name: str, server: McpServerConfig) -> dict[str, Any]:
    """Compile a single MCP server to a serializable runtime dictionary."""
    if server.url:
        result: dict[str, Any] = {
            "name": name,
            "transport": "http",
            "url": server.url,
        }
        if server.headers:
            result["headers"] = dict(server.headers)
        _append_tool_filters(result, server)
        return result

    result = {
        "name": name,
        "transport": "stdio",
        "command": server.command,
        "args": list(server.args),
    }
    if server.env:
        result["env"] = dict(server.env)
    if server.env_from_secret_manager:
        result["envFromSecretManager"] = dict(server.env_from_secret_manager)
    _append_tool_filters(result, server)
    return result


def compile_mcp_servers_to_ir(mcp_config: McpConfig | dict[str, Any]) -> tuple[McpServerIR, ...]:
    """Compile mcp.json to frozen MCP server IR."""
    config = mcp_config if isinstance(mcp_config, McpConfig) else parse_mcp_dict(mcp_config)
    servers: list[McpServerIR] = []
    for name, server in config.mcp_servers.items():
        server_dict = compile_mcp_server_dict(name, server)
        transport = server_dict.get("transport", "stdio")
        ir_transport: str
        if transport == "http":
            ir_transport = "streamable-http"
        elif transport == "sse":
            ir_transport = "sse"
        else:
            ir_transport = "stdio"
        servers.append(
            McpServerIR(
                name=str(server_dict["name"]),
                transport=ir_transport,  # type: ignore[arg-type]
                command=server_dict.get("command"),
                args=tuple(server_dict.get("args") or ()),
                url=server_dict.get("url"),
                env={str(key): str(value) for key, value in (server_dict.get("env") or {}).items()},
                headers={
                    str(key): str(value)
                    for key, value in (server_dict.get("headers") or {}).items()
                },
                enabled_tools=tuple(server_dict.get("enabledTools") or ()),
                disabled_tools=tuple(server_dict.get("disabledTools") or ()),
            )
        )
    return tuple(servers)


def compile_mcp_servers(mcp_config: McpConfig | dict[str, Any]) -> list[dict[str, Any]]:
    """Compile mcp.json to runtime-compatible server dictionaries."""
    config = mcp_config if isinstance(mcp_config, McpConfig) else parse_mcp_dict(mcp_config)
    return [compile_mcp_server_dict(name, server) for name, server in config.mcp_servers.items()]


def _sdk_kwargs_from_server_dict(server: dict[str, Any]) -> dict[str, Any]:
    """Build SDK MCP server constructor kwargs from a compiled server dict."""
    if server.get("envFromSecretManager"):
        raise CompilationError(
            "MCP server envFromSecretManager is not supported by the current Antigravity SDK."
        )
    if server.get("enabledTools") and server.get("disabledTools"):
        raise CompilationError("MCP server enabledTools and disabledTools are mutually exclusive.")

    kwargs: dict[str, Any] = {"name": server["name"]}
    if server.get("enabledTools"):
        kwargs["enabled_tools"] = list(server["enabledTools"])
    if server.get("disabledTools"):
        kwargs["disabled_tools"] = list(server["disabledTools"])
    return kwargs


def try_compile_mcp_sdk_objects_from_compiled(servers: list[dict[str, Any]]) -> list[Any]:
    """Compile MCP server IR dicts to SDK objects when google-antigravity is available."""
    try:
        from google.antigravity import types

        mcp_stdio_server = types.McpStdioServer
        mcp_streamable_http_server = getattr(types, "McpStreamableHttpServer", None)
    except ImportError:
        return servers

    sdk_servers: list[Any] = []
    for server in servers:
        kwargs = _sdk_kwargs_from_server_dict(server)
        if server.get("transport") == "http":
            if mcp_streamable_http_server is None:
                sdk_servers.append(server)
                continue
            kwargs["url"] = server["url"]
            if server.get("headers"):
                kwargs["headers"] = dict(server["headers"])
            sdk_servers.append(mcp_streamable_http_server(**kwargs))
            continue

        kwargs["command"] = server["command"]
        kwargs["args"] = list(server.get("args", []))
        if server.get("env"):
            kwargs["env"] = dict(server["env"])
        sdk_servers.append(mcp_stdio_server(**kwargs))
    return sdk_servers


def validate_mcp_json(path: Path, *, production: bool = False) -> McpConfig:
    """Parse and validate mcp.json."""
    config = parse_mcp_json(path)
    assert_mcp_security(config, production=production)
    return config


def validate_mcp_dict(data: dict[str, Any], *, production: bool = False) -> McpConfig:
    """Parse and validate mcp.json content from a dictionary."""
    config = parse_mcp_dict(data)
    assert_mcp_security(config, production=production)
    return config
