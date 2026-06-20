# Validation and evals

This guide covers validation levels and profiles for `antigravity-agentkit validate`, the eval suite YAML format, running evals in mock mode, and a CI integration pattern.

**Related guides:** [Getting started](01-getting-started.md) · [Agent manifest reference](03-agent-manifest-reference.md) · [MCP integration](05-mcp-integration.md) · [Skills and subagents](06-skills-and-subagents.md) · [Policies and governance](07-policies-and-governance.md)

## Validation levels

`antigravity-agentkit validate` checks an agent directory at increasing depth. Levels are **cumulative**—each level includes all checks from lower levels.

| Level      | Flag                       | What it checks                                                         |
| ---------- | -------------------------- | ---------------------------------------------------------------------- |
| `syntax`   | `--level syntax`           | Parse `agent.yaml`, `SYSTEM.md`, `mcp.json` JSON, `policies.yaml` YAML |
| `schema`   | `--level schema` (default) | Skill frontmatter, subagent definitions, MCP schema, policies schema   |
| `security` | `--level security`         | MCP security rules, production policy requirements, admission policy   |
| `cloud`    | `--level cloud`            | Vertex config, `deployment.serviceAccount`, gateway warnings           |
| `full`     | `--level full`             | All of the above (equivalent to `cloud` for current checks)            |

```bash
# Default: schema validation under dev-open profile
uv run antigravity-agentkit validate examples/mcp

# Security-focused check
uv run antigravity-agentkit validate examples/mcp --level security

# Full governance + cloud check
uv run antigravity-agentkit validate examples/mcp --level full --profile prod-readonly
```

If validation fails, AgentKit prints diagnostics and exits with code 1:

```text
ERROR AGK-CLOUD-002: Profile 'prod-readonly' requires deployment.serviceAccount
  file: agent.yaml
  path: $.spec.deployment.serviceAccount

Validation passed.
```

On success, the CLI prints `Validation passed.` and exits 0.

### Validation profiles

Profiles control governance strictness. They are orthogonal to levels but interact at `security` and `cloud`:

| Profile                     | CLI value             | Typical use                              |
| --------------------------- | --------------------- | ---------------------------------------- |
| Development (open)          | `dev-open`            | Local iteration; MCP issues are warnings |
| Development (restricted)    | `dev-restricted`      | Pre-commit; MCP issues are errors        |
| Production (read-only)      | `prod-readonly`       | Deployed read-only agents                |
| Production (human approval) | `prod-human-approval` | Agents with approval gates               |
| Production (locked)         | `prod-locked`         | Maximum lockdown                         |

```bash
uv run antigravity-agentkit validate <path> --level <level> --profile <profile>
```

See [Policies and governance](07-policies-and-governance.md) for `prod-readonly` requirements (policies file, service account, dangerous-tool denies).

### Diagnostic format

Each diagnostic includes a stable code, message, and optional file/path:

```text
<LEVEL> <CODE>: <message>
  file: <path>
  path: <json-pointer>
  hint: <optional hint>
```

Codes follow the pattern `AGK-<AREA>-<NNN>`. Common examples:

| Code               | Area   | Summary                                    |
| ------------------ | ------ | ------------------------------------------ |
| AGK-LOAD-001       | Load   | File load failure                          |
| AGK-SCHEMA-001     | Schema | Manifest or component schema error         |
| AGK-VALID-001      | Syntax | YAML/JSON parse error                      |
| AGK-MCP-001–005    | MCP    | MCP syntax, schema, security, admission    |
| AGK-POLICY-001–007 | Policy | Policies syntax, schema, prod requirements |
| AGK-CLOUD-001–003  | Cloud  | Vertex, service account, gateway           |

Syntax errors short-circuit validation: if `agent.yaml` cannot be parsed, schema checks are skipped.

## Declaring eval suites

List eval files in `agent.yaml`:

```yaml
spec:
  evals:
    files:
      - evals/smoke.yaml
```

Each file is an **eval suite**—a versioned document with one or more test cases.

### Suite format

From [`examples/mcp/evals/smoke.yaml`](../../examples/mcp/evals/smoke.yaml):

```yaml
version: 1
cases:
  - name: metadata-discovery
    input: "List approved finance datasets and summarize available tables."
    expected:
      mustMention:
        - "dataset"
        - "table"
      mustNotMention:
        - "raw password"
    tools:
      allowed:
        - mcp.bigquery-metadata.list_datasets
        - mcp.bigquery-metadata.list_tables
      denied:
        - run_command
```

### Case fields

| Field      | Required | Description                                     |
| ---------- | -------- | ----------------------------------------------- |
| `name`     | Yes      | Unique identifier within the suite              |
| `input`    | Yes      | Simulated user prompt                           |
| `expected` | No       | Assertion block (defaults to empty)             |
| `tools`    | No       | Tool allow/deny constraints (defaults to empty) |

### Expected assertions (`expected`)

| Field                 | YAML key            | Description                                                 |
| --------------------- | ------------------- | ----------------------------------------------------------- |
| `must_mention`        | `mustMention`       | Phrases that must appear in the response (case-insensitive) |
| `must_not_mention`    | `mustNotMention`    | Phrases that must not appear                                |
| `max_tool_calls`      | `maxToolCalls`      | Maximum number of tool invocations                          |
| `max_latency_seconds` | `maxLatencySeconds` | Latency ceiling (reserved for live evals)                   |
| `forbidden_patterns`  | `forbiddenPatterns` | Regex patterns that must not match the response             |

### Tool constraints (`tools`)

| Field     | Description                                                 |
| --------- | ----------------------------------------------------------- |
| `allowed` | Only these tools may be used; any other tool fails the case |
| `denied`  | These tools must not be used                                |

Eval tool checks also consult `policies.yaml`: if a tool resolves to `deny` under the agent's policies, the case fails even when not listed in `tools.denied`.

Case names must be unique within a suite. Duplicate names raise a schema validation error.

## Running evals

AgentKit runs evals in **deterministic mock mode**—no live model or MCP connection required. The runner synthesizes a predictable response from the case input, system instructions, and expected assertions, then checks all constraints.

```bash
# Run all declared suites
uv run antigravity-agentkit eval examples/mcp

# Filter by suite filename (comma-separated, substring match)
uv run antigravity-agentkit eval examples/mcp --suite smoke
```

Example output:

```text
PASS evals/smoke.yaml:metadata-discovery

1/1 passed
```

On failure:

```text
FAIL evals/smoke.yaml:metadata-discovery
  - Expected response to mention 'dataset'

0/1 passed
Error: Evaluation failures:
evals/smoke.yaml:metadata-discovery: Expected response to mention 'dataset'
```

The CLI exits with code 1 when any case fails.

### Suite filter

`--suite` accepts a comma-separated list of substrings matched against the suite file path (case-insensitive). `--suite smoke` runs `evals/smoke.yaml`; `--suite integration` runs nothing if no file matches.

### Mock mode behavior

Understanding mock mode helps you write effective evals:

- The mock response includes the case `input`, tokens from `SYSTEM.md`, and any `mustMention` phrases (so mention assertions are designed to pass when configured correctly).
- The mock uses the first `tools.allowed` entry as the simulated tool call, or `read_skill` when no allowed tools are specified.
- Policy resolution runs against the agent's `policies.yaml`.

Mock mode is ideal for CI smoke tests and governance regression checks, not for evaluating model quality.

## CI example

Add validation and eval steps to your pipeline after installing dependencies:

```bash
#!/usr/bin/env bash
set -euo pipefail

AGENT_DIR="examples/mcp"

# Install project dependencies
uv sync

# Schema + security validation (development profile)
uv run antigravity-agentkit validate "${AGENT_DIR}" --level security --profile dev-restricted

# Production governance gate (expect failure until serviceAccount is configured)
# uv run antigravity-agentkit validate "${AGENT_DIR}" --level full --profile prod-readonly

# Deterministic eval smoke tests
uv run antigravity-agentkit eval "${AGENT_DIR}" --suite smoke
```

A stricter production gate for agents that are deployment-ready:

```bash
#!/usr/bin/env bash
set -euo pipefail

AGENT_DIR="${1:?Usage: $0 <agent-directory>}"

uv sync

uv run antigravity-agentkit validate "${AGENT_DIR}" \
  --level full \
  --profile prod-readonly

uv run antigravity-agentkit eval "${AGENT_DIR}"
```

Integrate these commands into GitHub Actions, Cloud Build, or any CI runner that has Python and `uv` available. The repository's own test workflow runs `uv run bash dev/test_python.sh`, which includes unit tests for validation and eval logic.

## JSON Schema reference

Formal schemas for manifest and eval structures live under [`docs/schemas/`](../schemas/):

- [`agent.schema.json`](../schemas/agent.schema.json) — `agent.yaml`
- [`policies.schema.json`](../schemas/policies.schema.json) — `policies.yaml`
- [`eval.schema.json`](../schemas/eval.schema.json) — `evals/*.yaml`

Use `antigravity-agentkit validate --level schema` to verify conformance without running security or cloud checks.
