# Your First Agent

This guide walks through creating, validating, compiling, and running a minimal agent. We use the same layout as [`examples/hello_world/`](../../examples/hello_world/) so you can compare your work against a known-good reference.

**Previous:** [Getting started](01-getting-started.md) · **Next:** [Agent manifest reference](03-agent-manifest-reference.md)

## What you will build

A two-file agent:

- `agent.yaml` — declares identity, runtime, and where to find instructions
- `SYSTEM.md` — tells the model who it is and how to behave

No MCP servers, skills, or policies yet. That keeps the loop short: edit → validate → run.

## Step 1: Scaffold with `antigravity-agentkit init`

From any parent directory:

```bash
antigravity-agentkit init my-agent
```

This creates:

```text
my-agent/
  agent.yaml
  SYSTEM.md
```

The generated `agent.yaml` matches the shape used in hello_world:

```yaml
apiVersion: antigravity-agentkit.dev/v1alpha1
kind: Agent
metadata:
  name: my-agent
  displayName: My Agent
  description: Minimal Antigravity AgentKit example.
spec:
  runtime:
    framework: antigravity
    vertex:
      enabled: false
  instructions:
    system: SYSTEM.md
```

If the directory already exists, init fails with `Directory already exists`. Pick a new name or remove the old folder.

Use `--output-dir` / `-o` to create the agent somewhere other than the current working directory:

```bash
antigravity-agentkit init my-agent -o ~/agents
```

## Step 2: Edit `SYSTEM.md`

Open `SYSTEM.md` and define role, responsibilities, and safety rules. The hello_world example uses this structure:

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

Keep instructions specific enough to steer behavior, short enough to fit in context. See [System instructions](04-system-instructions.md) for patterns used in governed agents.

## Step 3: Validate

```bash
antigravity-agentkit validate my-agent
```

On success:

```text
Validation passed.
```

Run deeper checks as you add MCP or policies:

```bash
antigravity-agentkit validate my-agent --level security
antigravity-agentkit validate my-agent --level full --profile dev-restricted
```

Validation prints diagnostics before exiting. Fix errors (red) first; warnings may be acceptable in development.

## Step 4: Compile

```bash
antigravity-agentkit compile my-agent
```

Example output:

```json
{
  "systemInstructionsLength": 187,
  "mcpServerCount": 0,
  "toolCount": 0,
  "policyCount": 0,
  "vertex": { "enabled": false }
}
```

Write the summary to a file:

```bash
antigravity-agentkit compile my-agent -o /tmp/compiled.json
```

Compile does not call a model. It only proves the directory compiles to SDK-ready configuration.

## Step 5: Run with `--prompt`

Install the Antigravity SDK if you have not already:

```bash
pip install 'antigravity-agentkit[antigravity]'
# or, in this repo: uv sync --extra antigravity
```

Run one chat turn:

```bash
antigravity-agentkit run my-agent --prompt "Hello"
```

The CLI prints the model response to stdout. For production gates:

```bash
antigravity-agentkit run my-agent --prompt "Hello" --production
```

## Step 5b: Chat interactively

For a multi-turn conversation in one session, use `chat` instead of `run`:

```bash
antigravity-agentkit chat my-agent
```

Optional first message, then continue at the `You:` prompt:

```bash
antigravity-agentkit chat my-agent --prompt "Hello"
```

Type `exit` or `quit` (or press Ctrl-C or Ctrl-D) to leave. Use `--interactive` when `policies.yaml` requires human approval for tool calls.

## Walkthrough: hello_world example

You can skip scaffolding and use the repository example directly:

```bash
antigravity-agentkit validate examples/hello_world
antigravity-agentkit compile examples/hello_world
antigravity-agentkit run examples/hello_world --prompt "Hello"
```

Compare your `my-agent` files to:

- [`examples/hello_world/agent.yaml`](../../examples/hello_world/agent.yaml)
- [`examples/hello_world/SYSTEM.md`](../../examples/hello_world/SYSTEM.md)

They should be nearly identical if you only changed the agent name.

## Optional next steps

| Command                                                                         | When to use                 |
| ------------------------------------------------------------------------------- | --------------------------- |
| `antigravity-agentkit eval my-agent`                                            | After adding `evals/*.yaml` |
| `antigravity-agentkit package my-agent`                                         | Before deployment           |
| `antigravity-agentkit deploy my-agent --project ID --location REGION --dry-run` | Inspect deployment config   |

For a full-featured reference, open [`examples/mcp/`](../../examples/mcp/) and read [Agent manifest reference](03-agent-manifest-reference.md).

## Troubleshooting

### `Directory already exists`

`antigravity-agentkit init` refuses to overwrite. Remove the folder or choose another name.

### `Agent manifest not found` / `Agent directory not found`

- Pass the directory that contains `agent.yaml`, not a parent path.
- Check spelling and that you are in the right working directory.

### `google-antigravity is not installed`

`run` (and compile paths that materialize SDK objects) need the optional extra:

```bash
pip install 'antigravity-agentkit[antigravity]'
```

`validate` and `compile` JSON summary work without it.

### Schema validation errors

Typical causes:

- Wrong `apiVersion` (must be `antigravity-agentkit.dev/v1alpha1`)
- Missing `metadata.name` or `spec.instructions.system`
- Invalid YAML indentation under `spec`

Compare against [agent.schema.json](../schemas/agent.schema.json) or a working `agent.yaml`.

### `SYSTEM.md` not found

The path in `spec.instructions.system` is relative to the agent directory. If you rename the file, update `agent.yaml`.

### Validation passed but run fails

- Confirm credentials and network access for your chosen model backend.
- Enable Vertex in `spec.runtime.vertex` only when project and location are configured.
- Try `antigravity-agentkit validate my-agent --level full` to surface security or cloud issues.

### Empty or unexpected model output

- Strengthen `SYSTEM.md` (role, format, safety).
- Use a more capable `spec.runtime.model` when you add one (see bigquery example: `gemini-2.5-pro`).

## Checklist

- [ ] `antigravity-agentkit init` created `agent.yaml` and `SYSTEM.md`
- [ ] `SYSTEM.md` defines role and safety rules
- [ ] `antigravity-agentkit validate` passes
- [ ] `antigravity-agentkit compile` shows expected counts
- [ ] `antigravity-agentkit run --prompt "…"` returns a response (with antigravity extra installed)

---

**Previous:** [Getting started](01-getting-started.md) · **Next:** [Agent manifest reference](03-agent-manifest-reference.md)
