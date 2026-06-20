# Agent Manifest Reference

The `agent.yaml` file is the typed manifest for an agent directory. AgentKit validates it against [`agent.schema.json`](../schemas/agent.schema.json) and uses it to locate instructions, MCP config, skills, policies, and eval suites.

**Previous:** [Your first agent](02-your-first-agent.md) · **Next:** [System instructions](04-system-instructions.md)

## Top-level structure

Every manifest has four conceptual layers:

```yaml
apiVersion: antigravity-agentkit.dev/v1alpha1 # API version (fixed)
kind: Agent # Resource kind (fixed)
metadata: # Identity and catalog fields
  name: my-agent
spec: # Runtime, wiring, governance
  instructions:
    system: SYSTEM.md
```

| Field        | Required        | Description                                    |
| ------------ | --------------- | ---------------------------------------------- |
| `apiVersion` | Yes (defaulted) | Must be `antigravity-agentkit.dev/v1alpha1`    |
| `kind`       | Yes (defaulted) | Must be `Agent`                                |
| `metadata`   | Yes             | Name, display name, description, owner, labels |
| `spec`       | Yes             | Behavioral and operational configuration       |

The schema marks `metadata` and `spec` as required. Within `spec`, only `instructions` is required; other sections are optional.

## Manifest vs filesystem

AgentKit combines manifest references with conventional directory layout. Not every asset needs a manifest entry.

| Asset               | Manifest required?               | Default path     | Auto-discover?                                   |
| ------------------- | -------------------------------- | ---------------- | ------------------------------------------------ |
| System instructions | Yes (`spec.instructions.system`) | —                | No                                               |
| MCP                 | Yes (`spec.mcp` block)           | `mcp.json`       | No                                               |
| Policies            | Yes (`spec.policies` block)      | `policies.yaml`  | No                                               |
| Skills              | No                               | `skills/`        | Yes when `spec.skills.local` is omitted or empty |
| Subagents           | No                               | `subagents/*.md` | Yes when `spec.subagents` is omitted or empty    |
| Evals               | Yes (`spec.evals.files`)         | —                | No                                               |

`spec.mcp.file` and `spec.policies.file` default to `mcp.json` and `policies.yaml` when those blocks are present. Governance features (MCP admission policy, default-deny policies, eval suites) stay **manifest-gated** so reviewers see an explicit opt-in. See [Skills and subagents](06-skills-and-subagents.md) for discovery vs explicit skill listing.

## metadata

```yaml
metadata:
  name: mcp example # Required; max 64 chars
  displayName: BigQuery Metadata Agent
  description: Governed BigQuery metadata inspection and SQL review agent.
  owner: data-platform # Optional owning team
  labels: # Optional key/value tags
    domain: data
    criticality: medium
```

Use `name` as the stable identifier (DNS-like: lowercase, hyphens). `displayName` and `description` appear in catalogs and deployment UIs.

## spec.runtime

Configures the Antigravity framework, model, Vertex AI, and capability mode.

```yaml
spec:
  runtime:
    framework: antigravity # Only supported value
    model: gemini-2.5-pro # Optional model id
    vertex:
      enabled: false
      project: my-gcp-project # When vertex.enabled is true
      location: us-central1
    capabilities:
      mode: restricted # open | restricted | locked
      enabledTools: [] # Optional builtin tool allowlist
      disabledTools: [] # Optional builtin tool denylist
      enableSubagents: true # Optional; defaults true when subagents are declared
```

| Field                          | Default       | Notes                                       |
| ------------------------------ | ------------- | ------------------------------------------- |
| `framework`                    | `antigravity` | Constant in schema                          |
| `model`                        | SDK default   | Set explicitly for production agents        |
| `vertex.enabled`               | `false`       | Enable for Vertex AI / Gemini Enterprise    |
| `capabilities.mode`            | `restricted`  | `open`, `restricted`, or `locked` preset    |
| `capabilities.enabledTools`    | `[]`          | Builtin tools to expose (e.g. `search_web`) |
| `capabilities.disabledTools`   | `[]`          | Builtin tools to hide from the agent        |
| `capabilities.enableSubagents` | auto          | Set `true` when subagents are declared      |

`locked` mode adds default `disabledTools` for `run_command`, `create_file`, and `edit_file` when explicit lists are omitted. Builtin tool names use snake_case identifiers such as `view_file`, `run_command`, and `search_web`.

Minimal agents often leave `model` unset and keep `vertex.enabled: false` for local development.

## spec.instructions

```yaml
spec:
  instructions:
    system: SYSTEM.md
```

`system` is a path relative to the agent directory. AgentKit loads this file and may append a skill index section when local skills are declared. See [System instructions](04-system-instructions.md).

## spec.mcp

References an MCP server configuration file and optional admission policy.

```yaml
spec:
  mcp:
    file: mcp.json # Default: mcp.json
    admissionPolicy:
      allowedServers:
        - bigquery-metadata
```

`admissionPolicy.allowedServers` is an allowlist used in production validation. Server names must match keys under `mcpServers` in `mcp.json`. See [`examples/mcp/mcp.json`](../../examples/mcp/mcp.json).

## spec.skills

Local directories and registry-backed skills:

```yaml
spec:
  skills:
    local:
      - skills/bigquery-analysis
    registry:
      - name: published-skill
        revision: default
        mode: pinned # pinned | floating
```

Each local path must contain a `SKILL.md` with YAML frontmatter (`name`, `description`). The compiler injects a skill index into system instructions and exposes a `read_skill` helper tool.

Publish a skill package:

```bash
antigravity-agentkit publish-skill skills/bigquery-analysis --project ID --location REGION
```

## spec.subagents

Delegate work to markdown-defined or remote subagents:

```yaml
spec:
  subagents:
    - name: sql-reviewer
      type: markdown # markdown | remote
      file: subagents/sql-reviewer.md
      tools:
        - mcp.bigquery-metadata.get_table_metadata
        - mcp.bigquery-metadata.dry_run_query
```

| Field   | Required           | Notes                                   |
| ------- | ------------------ | --------------------------------------- |
| `name`  | Yes                | Unique subagent id                      |
| `type`  | Default `markdown` | `remote` uses `registryRef` and `auth`  |
| `file`  | For markdown       | Path to `.md` with frontmatter          |
| `tools` | Optional           | Allowlist of tools the subagent may use |

Markdown subagents compile into delegation tools on the parent agent.

## spec.policies

```yaml
spec:
  policies:
    file: policies.yaml # Default: policies.yaml
```

Policy documents are validated against [`policies.schema.json`](../schemas/policies.schema.json). Example excerpt from the BigQuery agent:

```yaml
default: deny

allow:
  - tool: view_file
  - tool: mcp.bigquery-metadata.list_datasets

askUser:
  - tool: mcp.bigquery-metadata.run_query
    when:
      risk: medium

deny:
  - tool: run_command
  - tool: write_file
```

Policies compile to Antigravity SDK policy objects during `compile` and `run`.

Deployment settings (scaling, service account, target) live in **`deployment.yaml`**, not in `agent.yaml`. See [Packaging and deployment](09-packaging-and-deployment.md).

## spec.registry

Controls Agent Registry, Skill Registry, and MCP server registration (`agentRegistry.enabled`, `skillRegistry.publishLocalSkills`, `mcpServers.register`). Emit metadata with:

```bash
antigravity-agentkit register my-agent --project ID --location REGION -o registry.json
```

## spec.evals

```yaml
spec:
  evals:
    files:
      - evals/smoke.yaml
```

Eval suites conform to [`eval.schema.json`](../schemas/eval.schema.json). Run them in deterministic mock mode:

```bash
antigravity-agentkit eval my-agent
antigravity-agentkit eval my-agent --suite smoke
```

## Minimal vs production manifest

### Minimal (hello_world)

```yaml
apiVersion: antigravity-agentkit.dev/v1alpha1
kind: Agent
metadata:
  name: hello-world
  displayName: Hello Agent
  description: Minimal Antigravity AgentKit example.
spec:
  runtime:
    framework: antigravity
    vertex:
      enabled: false
  instructions:
    system: SYSTEM.md
```

Source: [`examples/hello_world/agent.yaml`](../../examples/hello_world/agent.yaml)

### Production-style (mcp example)

The full manifest adds `model`, `capabilities`, `mcp`, `skills`, `subagents`, `policies`, and `evals`. Copy from the repository rather than duplicating it here:

[`examples/mcp/agent.yaml`](../../examples/mcp/agent.yaml)

That directory also includes `mcp.json`, `policies.yaml`, skills, subagents, and eval suites.

## Schema authority

When this guide and the schema disagree, trust the schema:

- [`../schemas/agent.schema.json`](../schemas/agent.schema.json) — `AgentManifest`
- [`../schemas/policies.schema.json`](../schemas/policies.schema.json) — `PolicyDocument`
- [`../schemas/eval.schema.json`](../schemas/eval.schema.json) — `EvalSuite`

Validate after every manifest change:

```bash
antigravity-agentkit validate my-agent --level schema
antigravity-agentkit validate my-agent --level full --profile prod-readonly
```

---

**Previous:** [Your first agent](02-your-first-agent.md) · **Next:** [System instructions](04-system-instructions.md)
