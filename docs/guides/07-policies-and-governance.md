# Policies and governance

This guide explains `policies.yaml`—the default-deny tool governance layer—and how validation profiles enforce production requirements.

**Related guides:** [Getting started](01-getting-started.md) · [Agent manifest reference](03-agent-manifest-reference.md) · [MCP integration](05-mcp-integration.md) · [Skills and subagents](06-skills-and-subagents.md) · [Validation and evals](08-validation-and-evals.md)

## Why policies.yaml

Agents can call built-in tools, MCP tools, `read_skill`, and delegation tools. Without explicit rules, a compromised prompt or over-eager model could invoke dangerous operations. AgentKit compiles `policies.yaml` into Antigravity-compatible policy hooks that gate every tool call.

The recommended posture is **default deny**: allow only what the agent needs, deny everything else.

## File format

`policies.yaml` is a YAML mapping with five sections:

| Section           | Compiled decision  | Behavior                                          |
| ----------------- | ------------------ | ------------------------------------------------- |
| `default`         | —                  | Baseline when no rule matches (`allow` or `deny`) |
| `allow`           | `allow`            | Tool is permitted                                 |
| `deny`            | `deny`             | Tool is blocked                                   |
| `askUser`         | `ask_user`         | Prompt the user before executing                  |
| `requireApproval` | `require_approval` | Require explicit approval (e.g. high-cost query)  |

Each rule entry requires a `tool` key. Optional `when` clauses add conditions for `askUser` and `requireApproval` rules.

Reference the file from `agent.yaml`:

```yaml
spec:
  policies:
    file: policies.yaml
```

### Example: mcp example

From [`examples/mcp/policies.yaml`](../../examples/mcp/policies.yaml):

```yaml
default: deny

allow:
  - tool: view_file
  - tool: mcp.bigquery-metadata.list_datasets
  - tool: mcp.bigquery-metadata.get_table_metadata
  - tool: mcp.bigquery-metadata.dry_run_query

askUser:
  - tool: mcp.bigquery-metadata.run_query
    when:
      risk: medium

requireApproval:
  - tool: mcp.bigquery-metadata.run_query
    when:
      estimatedBytesProcessedGt: 10000000000

deny:
  - tool: run_command
  - tool: write_file
```

### Conditional rules (`when`)

The `when` block supports:

| Field                       | Type                        | Description                                   |
| --------------------------- | --------------------------- | --------------------------------------------- |
| `risk`                      | `low` \| `medium` \| `high` | Risk tier for ask/approval flows              |
| `estimatedBytesProcessedGt` | integer                     | Trigger when estimated bytes exceed threshold |

Example: medium-risk queries ask the user; queries estimated above 10 GB require approval.

### Tool naming conventions

| Tool kind           | Example identifier                       |
| ------------------- | ---------------------------------------- |
| Built-in            | `view_file`, `run_command`, `write_file` |
| MCP                 | `mcp.<server-name>.<tool_name>`          |
| Skill loader        | `read_skill`                             |
| Subagent delegation | `delegate_to_<subagent_name>`            |

Use the same identifiers in policies, subagent `tools` lists, and eval `tools.allowed` / `tools.denied` blocks.

### Default deny compilation

When `default: deny`, AgentKit appends a catch-all rule to the compiled output:

```json
{ "tool": "*", "decision": "deny", "default": true }
```

Explicit `allow` entries take precedence over the default for matching tools. Policy resolution order for a specific tool:

1. `deny`
2. `requireApproval`
3. `askUser`
4. `allow`
5. `default`

## Policy profiles

Validation profiles model how strictly an agent is governed. Pass `--profile` to `antigravity-agentkit validate`:

```bash
uv run antigravity-agentkit validate <path> --level security --profile <profile>
```

| Profile               | MCP security  | Policies required | Service account | Notes                                   |
| --------------------- | ------------- | ----------------- | --------------- | --------------------------------------- |
| `dev-open`            | Warnings only | No                | No              | Local development default               |
| `dev-restricted`      | Errors        | No                | No              | Stricter MCP; admission policy enforced |
| `prod-readonly`       | Errors        | **Yes**           | **Yes**         | Production read-only posture            |
| `prod-human-approval` | Errors        | **Yes**           | **Yes**         | Production with human-in-the-loop       |
| `prod-locked`         | Errors        | **Yes**           | **Yes**         | Maximum lockdown                        |

Profiles `prod-readonly`, `prod-human-approval`, and `prod-locked` trigger production governance checks when validation level includes `security` or higher.

### prod-readonly requirements

To pass `validate` under `prod-readonly` (at `--level security` or above), your agent needs:

#### 1. A policies file

`spec.policies.file` must point to a loadable `policies.yaml`. Without it, validation reports **AGK-POLICY-003**:

```text
ERROR AGK-POLICY-003: Production profile requires policies.yaml
```

The minimal [hello_world](../../examples/hello_world/) example has no policies file and fails this check under production profiles.

#### 2. deployment.serviceAccount

At `--level cloud` or `full`, production profiles require a service account in the manifest:

```yaml
spec:
  deployment:
    serviceAccount: my-agent-sa@my-project.iam.gserviceaccount.com
```

Missing service account produces **AGK-CLOUD-002**:

```text
ERROR AGK-CLOUD-002: Profile 'prod-readonly' requires deployment.serviceAccount
```

#### 3. Dangerous-tool deny rules (recommended)

Production profiles warn (**AGK-POLICY-007**) when `run_command`, `write_file`, or `delete_file` lack explicit `deny` entries:

```text
WARN AGK-POLICY-007: Production agent has no explicit deny rule for run_command
```

The mcp example explicitly denies `run_command` and `write_file`, so it does not trigger these warnings.

#### 4. MCP admission policy

Every MCP server in `mcp.json` must appear in `spec.mcp.admissionPolicy.allowedServers`. See [MCP integration](05-mcp-integration.md).

### Example: validating for production

```bash
# Security + policy requirements
uv run antigravity-agentkit validate examples/mcp \
  --level security \
  --profile prod-readonly

# Full check including cloud (service account)
uv run antigravity-agentkit validate examples/mcp \
  --level full \
  --profile prod-readonly
```

The mcp example passes under `dev-open` at all levels but fails `prod-readonly` at `cloud`/`full` until `deployment.serviceAccount` is added to `agent.yaml`—by design, to demonstrate the requirement.

## Diagnostic codes

AgentKit emits stable `AGK-*` codes for policy and governance issues:

| Code           | Level | When                                                                                       |
| -------------- | ----- | ------------------------------------------------------------------------------------------ |
| AGK-POLICY-001 | ERROR | Invalid YAML in `policies.yaml` (syntax level)                                             |
| AGK-POLICY-002 | ERROR | Policies fail schema validation                                                            |
| AGK-POLICY-003 | ERROR | Production profile but no `policies.yaml`                                                  |
| AGK-POLICY-007 | WARN  | Production profile missing explicit deny for `run_command`, `write_file`, or `delete_file` |

Related codes from other subsystems often appear alongside policy checks:

| Code          | Subsystem | Meaning                                              |
| ------------- | --------- | ---------------------------------------------------- |
| AGK-MCP-003   | MCP       | Security rule violation                              |
| AGK-MCP-005   | MCP       | Server not on admission allowlist                    |
| AGK-CLOUD-001 | Cloud     | `runtime.vertex.project` missing when Vertex enabled |
| AGK-CLOUD-002 | Cloud     | `deployment.serviceAccount` missing for prod profile |
| AGK-CLOUD-003 | WARN      | Agent Gateway enabled without `requiredEndpoints`    |

See [Validation and evals](08-validation-and-evals.md) for the complete validation level ladder.

## Authoring checklist

1. Set `default: deny` for production agents.
2. Add explicit `allow` entries for every tool the agent needs (built-in, MCP, `read_skill`, delegation tools).
3. Add explicit `deny` entries for `run_command`, `write_file`, and `delete_file`.
4. Use `askUser` and `requireApproval` with `when` clauses for risky MCP operations.
5. Reference MCP tools with the `mcp.<server>.<tool>` prefix consistently.
6. Run `antigravity-agentkit validate --level security --profile prod-readonly` before deploying.
