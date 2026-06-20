# Skills and subagents

This guide explains how to author local skill packages (`SKILL.md`), how progressive disclosure keeps system prompts compact, and how markdown subagents compile into delegation tools.

**Related guides:** [Getting started](01-getting-started.md) · [Agent manifest reference](03-agent-manifest-reference.md) · [System instructions](04-system-instructions.md) · [MCP integration](05-mcp-integration.md) · [Policies and governance](07-policies-and-governance.md) · [Validation and evals](08-validation-and-evals.md)

## Skills overview

Skills are reusable instruction packages stored as `SKILL.md` files. Each skill lives in its own directory under `skills/`:

```text
skills/
  bigquery-analysis/
    SKILL.md
```

Declare local skills in `agent.yaml`:

```yaml
spec:
  skills:
    local:
      - skills/bigquery-analysis
```

AgentKit loads each path, validates frontmatter, and makes skills available at compile time. The [mcp example](../../examples/mcp/) example includes a complete skill package.

## SKILL.md frontmatter

Every `SKILL.md` file starts with YAML frontmatter delimited by `---`:

```markdown
---
name: bigquery-analysis
description: Use this skill for BigQuery metadata inspection, SQL review, dry-run validation, and privacy-aware analytics workflows.
license: Apache-2.0
---

# BigQuery Analysis Skill

## When to use

...
```

### Required and optional fields

| Field         | Required | Rules                                                                                                 |
| ------------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `name`        | Yes      | Lowercase letters, digits, and hyphens; must start with a lowercase letter (e.g. `bigquery-analysis`) |
| `description` | Yes      | Non-blank, max 1024 characters; shown in the skill index                                              |
| `license`     | No       | SPDX-style license identifier                                                                         |

Unknown frontmatter keys are rejected at schema validation time. The `name` in frontmatter must match the skill's logical identity; when referenced from `agent.yaml`, the loaded skill is keyed by this name.

### Package layout

A minimal skill package contains only `SKILL.md`. You can add supporting files (references, scripts) alongside it, but AgentKit loads and validates the `SKILL.md` file itself:

```text
skills/my-skill/
  SKILL.md
  references/
    examples.md
```

Only paths listed under `spec.skills.local` are loaded for a given agent. AgentKit does not auto-discover skills unless you use the internal `discover_skills` helper during development tooling.

## Progressive disclosure and the skill index

Loading every skill's full body into the system prompt would waste context. AgentKit uses **progressive disclosure**:

1. At compile time, a compact **skill index** is injected into system instructions.
2. The index lists each skill's `name` and `description` only.
3. The agent calls the `read_skill` tool when it needs full instructions.

The injected index looks like this:

```markdown
## Available Skills

- **bigquery-analysis**: Use this skill for BigQuery metadata inspection, SQL review, dry-run validation, and privacy-aware analytics workflows.

Use the `read_skill` tool to load full skill instructions when needed.
```

This text is appended to `SYSTEM.md` content during compilation. The agent sees what skills exist and when to use them, but reads the full `SKILL.md` body only on demand.

## The read_skill tool

`read_skill` is an internal helper tool compiled into every agent that declares local skills. Its metadata includes the list of available skill names:

```json
{
  "name": "read_skill",
  "description": "Load full instructions for a named skill. Available skills: bigquery-analysis",
  "parameters": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "Skill name to load"
      }
    },
    "required": ["name"]
  }
}
```

At runtime, calling `read_skill` with `{"name": "bigquery-analysis"}` returns the full `SKILL.md` content (frontmatter and body). If the name is unknown, AgentKit returns an error listing available skills.

**Authoring tip:** Write the `description` in frontmatter so the index alone is enough for the model to decide _whether_ to load the skill. Put detailed procedures in the markdown body.

## Subagents overview

Subagents are specialized agents defined as markdown files with YAML frontmatter. They are declared in `agent.yaml`, compiled into the runtime configuration, and exposed to the Antigravity SDK via `capabilities.enableSubagents` plus an injected **Available Subagents** section in system instructions. When the installed SDK supports `SubagentConfig`, static subagent definitions are also passed directly to `LocalAgentConfig`.

```yaml
spec:
  subagents:
    - name: sql-reviewer
      type: markdown
      file: subagents/sql-reviewer.md
      tools:
        - mcp.bigquery-metadata.get_table_metadata
        - mcp.bigquery-metadata.dry_run_query
```

Place subagent files under `subagents/`:

```text
subagents/
  sql-reviewer.md
```

## Markdown subagent frontmatter

From [`examples/mcp/subagents/time-checker.md`](../../examples/mcp/subagents/time-checker.md):

```markdown
---
name: sql-reviewer
description: Reviews SQL for BigQuery correctness, cost, safety, and privacy.
tools:
  - mcp.bigquery-metadata.get_table_metadata
  - mcp.bigquery-metadata.dry_run_query
---

# SQL Reviewer

Review generated SQL before execution.

Return:

1. correctness issues,
2. cost risks,
3. privacy risks,
4. suggested corrected SQL if needed.
```

### Frontmatter fields

| Field         | Required | Description                                                                 |
| ------------- | -------- | --------------------------------------------------------------------------- |
| `name`        | Yes      | Must match `spec.subagents[].name` in `agent.yaml`                          |
| `description` | No       | Short summary; used as the delegation tool description                      |
| `tools`       | No       | Default tool allowlist for the subagent (can be overridden in `agent.yaml`) |

The markdown body becomes the subagent's `system_instructions`. Keep it focused on the subagent's role and output format.

### Name consistency

AgentKit validates that the `name` in the markdown frontmatter matches the `name` in `agent.yaml`. A mismatch produces a schema validation error during `antigravity-agentkit validate`.

Tools listed in `agent.yaml` under the subagent entry override tools from the file frontmatter when both are present.

## Delegation tools (delegate*to*\*)

Each loaded subagent compiles to a delegation tool named `delegate_to_<name>`, with hyphens converted to underscores:

| Subagent name  | Delegation tool            |
| -------------- | -------------------------- |
| `sql-reviewer` | `delegate_to_sql_reviewer` |

Compiled tool shape:

```json
{
  "name": "delegate_to_sql_reviewer",
  "description": "Reviews SQL for BigQuery correctness, cost, safety, and privacy.",
  "subagent": "sql-reviewer",
  "tools": [
    "mcp.bigquery-metadata.get_table_metadata",
    "mcp.bigquery-metadata.dry_run_query"
  ],
  "system_instructions": "Review generated SQL before execution.\n\nReturn:..."
}
```

The main agent invokes `delegate_to_sql_reviewer` to hand off a task. The subagent runs with its own system instructions and a restricted tool set.

Add delegation tools and `read_skill` to your [policies.yaml](07-policies-and-governance.md) `allow` list if you use default-deny governance.

## End-to-end example

The mcp example ties skills, subagents, and MCP together:

```text
examples/mcp/
  agent.yaml              # declares skills, subagents, mcp, policies
  SYSTEM.md
  mcp.json
  skills/bigquery-analysis/SKILL.md
  subagents/sql-reviewer.md
  policies.yaml           # allow/deny for MCP and built-in tools
  evals/smoke.yaml
```

Typical flow:

1. User asks for SQL review.
2. Main agent sees the skill index and calls `read_skill("bigquery-analysis")` for procedures.
3. Main agent calls `delegate_to_sql_reviewer` with the SQL draft.
4. Subagent uses `mcp.bigquery-metadata.dry_run_query` (allowed by its tool list and policies).

## Validation

Schema-level validation checks skill frontmatter, subagent frontmatter, and name consistency:

```bash
uv run antigravity-agentkit validate examples/mcp --level schema
```

Skills and subagents are validated as part of `schema` and all higher levels. See [Validation and evals](08-validation-and-evals.md).
