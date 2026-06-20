# Getting Started

Antigravity AgentKit lets you author enterprise agents as files—mostly Markdown and YAML—instead of imperative Python. You declare what the agent is, what it can access, and how it must behave; AgentKit validates those declarations and compiles them into objects the Antigravity SDK understands.

This guide covers installation, verification, and the high-level architecture. By the end you will have the `antigravity-agentkit` CLI on your PATH and a mental model of how source files become a runnable agent.

**Previous:** [Guides index](README.md) · **Next:** [Your first agent](02-your-first-agent.md)

## What AgentKit does

AgentKit sits between your agent directory and the [Google Antigravity SDK](https://github.com/google-antigravity/antigravity-sdk-python):

1. **Load** — Read `agent.yaml`, `SYSTEM.md`, and optional MCP, skill, policy, and eval files.
2. **Validate** — Check syntax, JSON Schema, security rules, and (optionally) cloud deployment config.
3. **Compile** — Produce a unified runtime configuration: system instructions, tools, MCP servers, and policies.
4. **Run / deploy** — Drive a local chat turn via the SDK, package for Agent Runtime, or emit registry metadata.

You keep agent behavior in version-controlled files. The compiler enforces structure so teams can review changes like any other config.

## Prerequisites

| Requirement          | Notes                                                                        |
| -------------------- | ---------------------------------------------------------------------------- |
| **Python 3.10+**     | See `.python-version` in the repo for the pinned version used in development |
| **uv** (recommended) | Fast dependency management; used by `make setup` in this repository          |
| **Terminal**         | All workflows are CLI-driven                                                 |

Optional for live model calls:

| Requirement                  | Notes                                                  |
| ---------------------------- | ------------------------------------------------------ |
| **Antigravity SDK**          | Install via the `antigravity` extra (see below)        |
| **Google Cloud credentials** | Needed when Vertex AI or cloud MCP servers are enabled |

Validation and compilation work without the Antigravity SDK. `antigravity-agentkit run` requires it.

## Package, CLI, and import names

| Name                     | Example                                                                   | Purpose                                     |
| ------------------------ | ------------------------------------------------------------------------- | ------------------------------------------- |
| **PyPI package & CLI**   | `pip install antigravity-agentkit` then `antigravity-agentkit validate …` | Same name for install and terminal commands |
| **Python import**        | `from antigravity_agentkit import AgentProject`                           | Programmatic API (underscores, not hyphens) |
| **Manifest API version** | `apiVersion: antigravity-agentkit.dev/v1alpha1`                           | Schema version in `agent.yaml`              |

## Install AgentKit

### End users (PyPI)

When the package is published:

```bash
pip install antigravity-agentkit
```

For local chat and SDK integration, add the optional runtime:

```bash
pip install 'antigravity-agentkit[antigravity]'
```

### Contributors (this repository)

Clone the repo and bootstrap the development environment:

```bash
git clone https://github.com/your-org/antigravity-agentkit.git
cd antigravity-agentkit
make setup
```

`make setup` installs CLI tooling via mise and creates a Python virtualenv with `uv sync`. Run commands through the venv:

```bash
uv run antigravity-agentkit --help
```

### Optional: Antigravity SDK extra

The core package depends only on validation and CLI libraries (`pydantic`, `jsonschema`, `typer`, etc.). The Antigravity SDK is optional:

```bash
# From a clone of this repo
uv sync --extra antigravity
```

Equivalent for pip users:

```bash
pip install 'antigravity-agentkit[antigravity]'
```

Without this extra, `antigravity-agentkit validate`, `compile`, and `eval` still work. `run` exits with a clear error:

```text
google-antigravity is not installed; install with pip install 'antigravity-agentkit[antigravity]'
```

## Verify installation

```bash
antigravity-agentkit --help
```

You should see subcommands including `init`, `validate`, `compile`, `run`, `eval`, `package`, `deploy`, `publish-skill`, and `register`.

Smoke-test against the bundled hello example (no SDK required for validate/compile):

```bash
antigravity-agentkit validate examples/hello_world
antigravity-agentkit compile examples/hello_world
```

A successful compile prints JSON summary fields such as `systemInstructionsLength`, `mcpServerCount`, and `toolCount`.

## Agent directory layout

An **agent directory** is the unit of authoring. A minimal layout:

```text
my-agent/
  agent.yaml      # Typed manifest (required)
  SYSTEM.md       # Core system instructions (required)
```

Optional files extend capability and governance:

```text
  mcp.json              # MCP server declarations
  skills/*/SKILL.md     # Skill packages
  subagents/*.md        # Local subagent definitions
  policies.yaml         # Tool and MCP policies
  evals/*.yaml          # Smoke and regression evaluations
```

See [Agent manifest reference](03-agent-manifest-reference.md) for every `agent.yaml` field.

## Architecture overview

```text
  ┌─────────────────────────────────────────────────────────┐
  │  Authoring (Markdown + YAML)                            │
  │  agent.yaml · SYSTEM.md · mcp.json · skills · policies  │
  └──────────────────────────┬──────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │  AgentKit                                               │
  │  loader → validator → compiler                          │
  └──────────────────────────┬──────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │  Antigravity SDK                                        │
  │  Agent(system, tools, mcp_servers, policies)            │
  └──────────────────────────┬──────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
        antigravity-agentkit run                   antigravity-agentkit deploy
     (local chat turn)            (Agent Runtime / registry)
```

**Markdown + YAML** — Human-readable source. `SYSTEM.md` holds role and safety instructions; `agent.yaml` wires runtime, MCP, skills, and policies.

**Compiler** — Merges system instructions with a skill index, resolves MCP and subagent delegation tools, and compiles policy documents into SDK policy objects.

**Antigravity SDK** — Executes the agent: model calls, tool use, and policy enforcement.

## Validation levels and profiles

`antigravity-agentkit validate` accepts depth and governance knobs:

```bash
antigravity-agentkit validate my-agent --level schema
antigravity-agentkit validate my-agent --level full --profile prod-readonly
```

| Flag        | Values                                                                              | Default    |
| ----------- | ----------------------------------------------------------------------------------- | ---------- |
| `--level`   | `syntax`, `schema`, `security`, `cloud`, `full`                                     | `schema`   |
| `--profile` | `dev-open`, `dev-restricted`, `prod-readonly`, `prod-human-approval`, `prod-locked` | `dev-open` |

Use `--production` with `compile` and `run` to apply production policy gates (stricter validation profile).

## What to do next

1. Follow [Your first agent](02-your-first-agent.md) to scaffold, validate, and run an agent end to end.
2. Skim [`examples/hello_world/`](../../examples/hello_world/) and [`examples/mcp/`](../../examples/mcp/).
3. Read [RFC 0001](../rfcs/0001-declarative-antigravity-agentkit.md) for design rationale.

---

**Previous:** [Guides index](README.md) · **Next:** [Your first agent](02-your-first-agent.md)
