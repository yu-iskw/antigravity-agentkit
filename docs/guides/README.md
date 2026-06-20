# Antigravity AgentKit — user guides

Step-by-step documentation for authoring, validating, packaging, deploying, and governing agents with AgentKit. For design rationale and roadmap, see [RFC 0001](../rfcs/0001-declarative-antigravity-agentkit.md). For machine-readable schemas, see [`docs/schemas/`](../schemas/).

## Who these guides are for

- **Application developers** building agents from `agent.yaml`, `SYSTEM.md`, and optional MCP/skills
- **Platform engineers** wiring CI validation, packaging, and Google Cloud deployment
- **Security and governance reviewers** auditing policies, admission rules, and production profiles

## Guide index

| #   | Guide                                                        | What you will learn                                               |
| --- | ------------------------------------------------------------ | ----------------------------------------------------------------- |
| 01  | [Getting started](01-getting-started.md)                     | Install AgentKit, verify the CLI, understand the compile pipeline |
| 02  | [Your first agent](02-your-first-agent.md)                   | Scaffold, validate, compile, and run a minimal agent              |
| 03  | [Agent manifest reference](03-agent-manifest-reference.md)   | Every `agent.yaml` field, minimal vs production manifests         |
| 04  | [System instructions](04-system-instructions.md)             | Writing effective `SYSTEM.md` for governed agents                 |
| 05  | [MCP integration](05-mcp-integration.md)                     | `mcp.json`, admission policies, MCP security rules                |
| 06  | [Skills and subagents](06-skills-and-subagents.md)           | `SKILL.md` packages, skill index, markdown subagents              |
| 07  | [Policies and governance](07-policies-and-governance.md)     | `policies.yaml`, default deny, validation profiles                |
| 08  | [Validation and evals](08-validation-and-evals.md)           | Validation levels, eval suites, CI gates                          |
| 09  | [Packaging and deployment](09-packaging-and-deployment.md)   | Source packages, deployment spec, dry-run deploy                  |
| 10  | [Registry and publishing](10-registry-and-publishing.md)     | Agent Registry metadata, Skill Registry zip, `skills.lock`        |
| 11  | [Python API](11-python-api.md)                               | `AgentProject`, `RuntimeAgent`, programmatic workflows            |
| 12  | [Production workflows](12-production-workflows.md)           | CI pipelines, dev→prod promotion, GitOps, checklist               |
| 13  | [Agent Platform evaluation](13-agent-platform-evaluation.md) | Two-layer eval: AgentKit mock gates + Platform quality loop       |

## Suggested learning paths

### Path A — New to AgentKit (start here)

1. [Getting started](01-getting-started.md)
2. [Your first agent](02-your-first-agent.md)
3. [Agent manifest reference](03-agent-manifest-reference.md)
4. [System instructions](04-system-instructions.md)

### Path B — Governed tool-using agent

1. [MCP integration](05-mcp-integration.md)
2. [Skills and subagents](06-skills-and-subagents.md)
3. [Policies and governance](07-policies-and-governance.md)
4. [Validation and evals](08-validation-and-evals.md)

### Path C — Ship to Google Cloud

1. [Packaging and deployment](09-packaging-and-deployment.md)
2. [Registry and publishing](10-registry-and-publishing.md)
3. [Production workflows](12-production-workflows.md)
4. [Agent Platform evaluation](13-agent-platform-evaluation.md)

### Path D — Embed in apps or CI

1. [Python API](11-python-api.md)
2. [Validation and evals](08-validation-and-evals.md)
3. [Production workflows](12-production-workflows.md)

## Examples in this repository

| Path                                                   | Guides |
| ------------------------------------------------------ | ------ |
| [`examples/hello_world/`](../../examples/hello_world/) | 01–04  |
| [`examples/mcp/`](../../examples/mcp/)                 | 03–12  |

## CLI quick reference

```bash
uv run antigravity-agentkit init <name>
uv run antigravity-agentkit validate <path> [--level full] [--profile prod-readonly]
uv run antigravity-agentkit compile <path> [--production]
uv run antigravity-agentkit run <path> --prompt "..."
uv run antigravity-agentkit chat <path> [--prompt "..."]
uv run antigravity-agentkit eval <path> [--suite smoke]
uv run antigravity-agentkit package <path> [--output-dir DIR]
uv run antigravity-agentkit deploy <path> --project ID --location REGION [--dry-run]
uv run antigravity-agentkit publish-skill <skill-dir> [--project ID] [--location REGION]
uv run antigravity-agentkit register <path> --project ID --location REGION [--output FILE]
```

See the [project README](../../README.md) for install and quick start. Repository development setup is in [CONTRIBUTING.md](../../CONTRIBUTING.md).
