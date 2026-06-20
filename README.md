# antigravity-agentkit

Declarative agent compiler and governance layer for the [Google Antigravity SDK](https://github.com/google-antigravity/antigravity-sdk-python).

Author enterprise agents as version-controlled files—`agent.yaml`, `SYSTEM.md`, optional MCP servers, skills, policies, and evals—instead of imperative Python. AgentKit validates those declarations against typed schemas, compiles them into Antigravity runtime configuration, and supports packaging for Google Cloud Agent Platform workflows.

## Install

**Requirements:** Python 3.10+

```bash
pip install antigravity-agentkit
```

For local chat against a live model (requires the Antigravity SDK):

```bash
pip install 'antigravity-agentkit[antigravity]'
```

Validation, compilation, and evals work without the optional SDK. The `run` command needs `[antigravity]`.

## Quick start

Scaffold a new agent, validate it, and compile runtime configuration:

```bash
antigravity-agentkit init my-agent
cd my-agent
antigravity-agentkit validate .
antigravity-agentkit compile .
```

Try the bundled minimal example (from a clone of this repository):

```bash
antigravity-agentkit validate examples/hello_world
antigravity-agentkit compile examples/hello_world
```

Run a single chat turn (requires `[antigravity]` and `GEMINI_API_KEY` or `GOOGLE_API_KEY`):

```bash
antigravity-agentkit run examples/hello_world --prompt "Hello"
```

## Agent directory layout

An **agent directory** is the unit of authoring:

```text
agent.yaml          # typed agent manifest
SYSTEM.md           # core system instructions
mcp.json            # MCP server declarations (optional)
skills/*/SKILL.md   # skill packages (optional)
subagents/*.md      # local subagent definitions (optional)
policies.yaml       # tool, MCP, and risk policies (optional)
evals/*.yaml        # smoke, regression, and governance evaluations (optional)
```

Manifest API version: `antigravity-agentkit.dev/v1alpha1`

| Layer              | Name                                            |
| ------------------ | ----------------------------------------------- |
| PyPI package & CLI | `antigravity-agentkit`                          |
| Python import      | `antigravity_agentkit`                          |
| Manifest           | `apiVersion: antigravity-agentkit.dev/v1alpha1` |

JSON Schema definitions: [`docs/schemas/`](docs/schemas/)

## CLI commands

| Command                                                                   | Description                                         |
| ------------------------------------------------------------------------- | --------------------------------------------------- |
| `antigravity-agentkit init <name>`                                        | Scaffold a minimal agent directory                  |
| `antigravity-agentkit validate <path>`                                    | Validate manifest, security rules, and cloud config |
| `antigravity-agentkit compile <path>`                                     | Compile to runtime configuration (JSON)             |
| `antigravity-agentkit run <path> --prompt <text>`                         | Run one local chat turn                             |
| `antigravity-agentkit eval <path>`                                        | Run evaluation suites (deterministic mock mode)     |
| `antigravity-agentkit package <path>`                                     | Build a deployable source package                   |
| `antigravity-agentkit deploy <path> --project <id> --location <region>`   | Deploy or emit deployment config                    |
| `antigravity-agentkit publish-skill <skill-dir>`                          | Validate and package a skill for Skill Registry     |
| `antigravity-agentkit register <path> --project <id> --location <region>` | Emit Agent Registry metadata                        |

Useful flags:

- `validate --level {syntax,schema,security,cloud,full}` — validation depth (default: `schema`)
- `validate --profile {dev-open,dev-restricted,prod-readonly,prod-human-approval,prod-locked}` — governance profile
- `compile --production` / `run --production` — apply production policy gates
- `deploy --dry-run` — emit deployment config without applying changes

## Examples

| Path                                             | Description                                          |
| ------------------------------------------------ | ---------------------------------------------------- |
| [`examples/hello_world/`](examples/hello_world/) | Minimal agent with `gemini-3-flash-preview`          |
| [`examples/skills/`](examples/skills/)           | Local `SKILL.md` packages and `read_skill`           |
| [`examples/subagents/`](examples/subagents/)     | Markdown subagent delegation                         |
| [`examples/mcp/`](examples/mcp/)                 | MCP clock server, policies, skills, subagents, evals |

See [`examples/README.md`](examples/README.md) for verification commands.

## Documentation

**Step-by-step guides** (basics through production): [`docs/guides/`](docs/guides/)

Suggested path for new users:

1. [Getting started](docs/guides/01-getting-started.md)
2. [Your first agent](docs/guides/02-your-first-agent.md)
3. [Agent manifest reference](docs/guides/03-agent-manifest-reference.md)

### Design and schemas

- [RFC 0001 — Declarative Antigravity AgentKit](docs/rfcs/0001-declarative-antigravity-agentkit.md)
- [JSON schemas](docs/schemas/)

### Python API

[Programmatic workflows](docs/guides/11-python-api.md) with `AgentProject`, `RuntimeAgent`, and related helpers.

## Contributing

Bug reports, feature requests, and pull requests are welcome. Development setup, tests, and release conventions are documented in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache License 2.0 — see [LICENSE](LICENSE).
