# System Instructions

`SYSTEM.md` is the core prompt for your agent. The manifest points to it via `spec.instructions.system`. AgentKit loads this file at compile time, merges in a skill index when local skills exist, and passes the result to the Antigravity SDK as system instructions.

**Previous:** [Agent manifest reference](03-agent-manifest-reference.md) · **Next:** [MCP integration](05-mcp-integration.md)

## How SYSTEM.md fits in the pipeline

```text
  SYSTEM.md  ──┐
               ├──► compiler ──► Antigravity SDK Agent
  skills/*/  ──┘      (optional skill index appended)
```

You edit Markdown; the compiler handles injection and length accounting (`systemInstructionsLength` in `antigravity-agentkit compile` output). Keep the file focused on behavior and tone. Wire tools, MCP, and policies in `agent.yaml` and sibling files—not in long tool JSON embedded in the prompt.

## Recommended sections

A structure that works well across minimal and governed agents:

| Section                      | Purpose                                            |
| ---------------------------- | -------------------------------------------------- |
| **Role**                     | One paragraph: who the agent is and its domain     |
| **Primary Responsibilities** | Numbered list of what it should do                 |
| **Safety Rules**             | Hard constraints: data handling, forbidden actions |
| **Response Format**          | Optional; how to structure replies                 |

Use Markdown headings (`# Role`, `# Safety Rules`) so diffs stay readable in review.

### Role

State identity and scope in plain language. Avoid vague superlatives; name the domain.

```markdown
# Role

You are a concise helpful assistant.
```

For governed data agents:

```markdown
# Role

You are a governed BigQuery metadata and SQL review agent.
```

### Primary Responsibilities

Ordered list of behaviors the agent should prioritize. Use verbs: inspect, draft, explain, escalate.

```markdown
# Primary Responsibilities

1. Answer questions clearly and briefly.
2. Ask clarifying questions when the request is ambiguous.
```

Data-platform example:

```markdown
# Primary Responsibilities

1. Help users inspect approved BigQuery metadata.
2. Draft SQL only after inspecting table metadata.
3. Prefer dry-run validation before query execution.
4. Explain assumptions and limitations.
```

### Safety Rules

Bullet list of non-negotiable constraints. Align these with `policies.yaml` so prompt and enforcement tell the same story.

```markdown
# Safety Rules

- Do not execute destructive operations.
- Do not expose secrets or credentials.
```

Governed example:

```markdown
# Safety Rules

- Do not request or expose raw PII unless explicitly approved by policy.
- Do not execute write operations.
- Do not use unapproved MCP tools.
```

### Response Format

Optional but valuable for enterprise agents where consistency matters.

```markdown
# Response Format

Use:

1. executive summary,
2. analysis,
3. assumptions,
4. risks,
5. next actions.
```

## Example: hello_world

Full [`examples/hello_world/SYSTEM.md`](../../examples/hello_world/SYSTEM.md):

```markdown
# Role

You are a concise helpful assistant.

# Primary Responsibilities

1. Answer questions clearly and briefly.
2. Ask clarifying questions when the request is ambiguous.

# Safety Rules

- Do not execute destructive operations.
- Do not expose secrets or credentials.
```

Paired manifest: [`examples/hello_world/agent.yaml`](../../examples/hello_world/agent.yaml) with only `spec.instructions.system: SYSTEM.md`.

This agent has no **Response Format** section—appropriate for a minimal demo.

## Example: mcp example

Full [`examples/mcp/SYSTEM.md`](../../examples/mcp/SYSTEM.md):

```markdown
# Role

You are a governed BigQuery metadata and SQL review agent.

# Primary Responsibilities

1. Help users inspect approved BigQuery metadata.
2. Draft SQL only after inspecting table metadata.
3. Prefer dry-run validation before query execution.
4. Explain assumptions and limitations.

# Safety Rules

- Do not request or expose raw PII unless explicitly approved by policy.
- Do not execute write operations.
- Do not use unapproved MCP tools.

# Response Format

Use:

1. executive summary,
2. analysis,
3. assumptions,
4. risks,
5. next actions.
```

Note how responsibilities reference workflow steps that match skills and subagents:

- **Inspect metadata** → MCP tools allowed in `policies.yaml`
- **Dry-run before execution** → `askUser` / `requireApproval` rules for `run_query`
- **SQL review** → `sql-reviewer` subagent in `agent.yaml`

Instructions describe intent; manifest and policies enforce it.

## Tips for governed agents

### Align prompt with policies

If `SYSTEM.md` says "do not execute write operations," ensure `policies.yaml` denies `write_file` and dangerous MCP tools. Reviewers should see the same rules in both places.

### Reference skills lightly

Skill bodies live in `skills/*/SKILL.md`. The compiler adds a skill index to system instructions. In `SYSTEM.md`, mention when to use skills at a high level; put procedures in the skill file.

Example skill frontmatter and body live at [`examples/mcp/skills/mcp-guide/SKILL.md`](../../examples/mcp/skills/mcp-guide/SKILL.md).

### Subagents get their own prompts

Delegation targets use separate markdown files with frontmatter, not sections in `SYSTEM.md`. Example: [`subagents/time-checker.md`](../../examples/mcp/subagents/time-checker.md).

Parent `SYSTEM.md` should say _when_ to delegate (e.g. before running SQL); subagent files say _how_ to review.

### Keep eval expectations in mind

Eval cases in `evals/*.yaml` often assert `mustMention` / `mustNotMention` strings. Write instructions that make those outcomes likely without keyword stuffing.

### Length and clarity

- Prefer short paragraphs and lists over walls of text.
- Put rarely needed detail in skills or linked docs.
- Run `antigravity-agentkit compile` and check `systemInstructionsLength` when trimming.

## What not to put in SYSTEM.md

| Avoid                            | Put it instead                        |
| -------------------------------- | ------------------------------------- |
| MCP server commands and env vars | `mcp.json`                            |
| Tool allow/deny lists            | `policies.yaml`                       |
| Model name and Vertex project    | `agent.yaml` `spec.runtime`           |
| Detailed SQL style guides        | Skills or subagent files              |
| Secrets and API keys             | Secret manager / env outside the repo |

## Editing workflow

1. Edit `SYSTEM.md` in your agent directory.
2. Validate: `antigravity-agentkit validate my-agent`
3. Compile: `antigravity-agentkit compile my-agent` (check instruction length).
4. Run: `antigravity-agentkit run my-agent --prompt "…"`
5. When behavior is stable, add or update `evals/*.yaml` and run `antigravity-agentkit eval my-agent`.

For production:

```bash
antigravity-agentkit validate my-agent --level full --profile prod-readonly
antigravity-agentkit run my-agent --prompt "…" --production
```

## Scaffold default

`antigravity-agentkit init` creates a minimal starter:

```markdown
# Role

You are a helpful agent.
```

Replace this with role, responsibilities, and safety rules before sharing the agent with others.

## Related guides

- [Your first agent](02-your-first-agent.md) — scaffold and run loop
- [Agent manifest reference](03-agent-manifest-reference.md) — `spec.instructions.system` and skills wiring
- [MCP integration](05-mcp-integration.md) — connect external tools

---

**Previous:** [Agent manifest reference](03-agent-manifest-reference.md) · **Next:** [MCP integration](05-mcp-integration.md)
