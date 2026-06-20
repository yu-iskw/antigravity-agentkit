# Python API

AgentKit exposes a small Python library for loading, validating, compiling, running, packaging, deploying, and registering agents. Use it in notebooks, services, and CI jobs when the CLI is not enough. For command-line equivalents, see [Getting started](01-getting-started.md).

Install the package (and optional Antigravity SDK):

```bash
uv sync
uv sync --extra antigravity   # required for create_agent() and run_chat()
```

## Public exports

`antigravity_agentkit` re-exports the main types and functions:

```python
from antigravity_agentkit import (
    AgentProject,
    AgentProjectData,
    CompiledAgentConfig,
    RuntimeAgent,
    compile_agent_config,
    compile_to_sdk_config,
    compile_sdk_policies,
    load_agent,
    load_agent_directory,
    validate_project,
    build_source_package,
    build_deployment_config,
    deploy,
    build_agent_registry_metadata,
    publish_skill,
    run_evals,
)
```

`load_agent(path)` is an alias for `AgentProject.load(path)`.

## `AgentProject` lifecycle

`AgentProject` is the high-level handle for an agent directory.

### Load

```python
from pathlib import Path
from antigravity_agentkit import AgentProject

project = AgentProject.load("examples/hello_world")
# or
project = AgentProject.load(Path("examples/hello_world"))

print(project.manifest.metadata.name)
print(project.data.system_instructions[:200])
```

`load()` reads `agent.yaml`, system instructions, MCP config, skills, subagents, policies, and eval files via `load_agent_directory()`.

### Validate

```python
# Development defaults: level="schema", profile="dev-restricted"
project.validate()

# Production gate (level="full", profile="prod-readonly")
project.validate(production=True)

# Explicit control
project.validate(level="security", profile="prod-locked")
```

`validate()` raises on failure (through `assert_valid_project`). For non-throwing diagnostics, use `validate_project()`:

```python
from antigravity_agentkit import validate_project

collector = validate_project(project.root, project.data, level="full", profile="prod-readonly")
if collector.has_errors():
    print(collector.format_all())
```

Profiles and levels are documented in [Validation and evals](08-validation-and-evals.md).

### Compile

```python
compiled = project.compile()
compiled_prod = project.compile(production=True)

print(len(compiled.system_instructions))
print(compiled.mcp_servers)
print(compiled.tools)
print(compiled.policies)
print(compiled.vertex)
```

`compile()` validates first, then returns a `CompiledAgentConfig` dataclass with rendered system instructions (including skill index), MCP server dicts, delegation tools, policy rules, and Vertex settings.

One-shot compile without holding a project:

```python
from antigravity_agentkit import compile_agent_config

compiled = compile_agent_config("examples/mcp", production=True)
sdk_config = compile_to_sdk_config(compiled)
```

`compile_to_sdk_config()` returns a `google.antigravity.LocalAgentConfig` when the SDK is installed.

### Create agent (live runtime)

```python
agent = project.create_agent()
agent_prod = project.create_agent(production=True)
interactive_agent = project.create_agent(interactive=True)

async def chat_once():
    async with agent:
        return await agent.chat("List datasets in the finance project.")

# Requires: pip install 'antigravity-agentkit[antigravity]'
```

`interactive=True` wires a real `ask_user` approval handler for `askUser` / `requireApproval` policies. The CLI equivalent is `antigravity-agentkit run --interactive`.

Requires `google-antigravity`. Raises `CompilationError` if the extra is missing.

### Package

```python
from antigravity_agentkit import AgentProject, build_source_package, load_deployment

project = AgentProject.load("src/antigravity_agentkit/tests/fixtures/ship_agent")
load_deployment(project.root)  # required before package

package_dir = build_source_package(project)
# default: <agent-root>/.build/<metadata.name>/

custom = build_source_package(project, output_dir="/tmp/my-agent-build")
```

See [Packaging and deployment](09-packaging-and-deployment.md) for output layout.

## `RuntimeAgent`

`RuntimeAgent` wraps `AgentProject` for a convenient local chat path.

```python
import asyncio
from antigravity_agentkit import RuntimeAgent

async def main():
    runtime = RuntimeAgent.from_directory("examples/hello_world")
    response = await runtime.run_chat("Hello!", production=False)
    print(await response.text())

    # Prompt for ask_user policy approvals:
    response = await runtime.run_chat("Delete prod data", interactive=True)

asyncio.run(main())
```

`from_directory(..., production=True)` calls `project.validate(production=True)` before constructing the wrapper. `run_chat()` calls `create_agent()` and `agent.chat(prompt)` inside an async context manager. Pass `interactive=True` when `policies.yaml` contains `askUser` or `requireApproval` rules.

### Policy compilation helper

If you build SDK agents manually from compiled policy dicts:

```python
from antigravity_agentkit import compile_sdk_policies

policies = compile_sdk_policies(compiled.policies)
# list of google.antigravity.policy objects
```

Non-interactive mode (the default) denies `ask_user` / `require_approval` tool calls via a default handler that returns `False`. Use `create_agent(interactive=True)`, `run_chat(..., interactive=True)`, or `antigravity-agentkit run --interactive` to approve interactively.

## Deploy and registry helpers

```python
from antigravity_agentkit import (
    AgentProject,
    build_source_package,
    build_deployment_config,
    deploy,
    build_agent_registry_metadata,
    publish_skill,
)
from antigravity_agentkit.deploy import load_deployment

project = AgentProject.load("src/antigravity_agentkit/tests/fixtures/ship_agent")
deployment = load_deployment(project.root)

package_path = build_source_package(project)
config = build_deployment_config(
    project, deployment, project_id="my-project", location="us-central1"
)

summary = deploy(
    project,
    deployment,
    "my-project",
    "us-central1",
    dry_run=True,
    output_path="/tmp/deployment-config.json",
)

metadata = build_agent_registry_metadata(project, deployment)
skill_result = publish_skill("path/to/skills/my-skill", project="my-project", location="us-central1")
```

See [Packaging and deployment](09-packaging-and-deployment.md) and [Registry and publishing](10-registry-and-publishing.md).

## Evaluations

```python
from antigravity_agentkit import run_evals

result = run_evals(project, suite_filter="smoke")
for case in result.cases:
    print(case.name, "PASS" if case.passed else "FAIL")
```

Eval YAML format: [Validation and evals](08-validation-and-evals.md).

## When to use CLI vs API

| Use CLI when                                          | Use Python API when                                      |
| ----------------------------------------------------- | -------------------------------------------------------- |
| You are exploring locally (`init`, `validate`, `run`) | CI needs programmatic pass/fail without shelling out     |
| Operators run one-off commands                        | You embed AgentKit in a service or notebook              |
| Shell scripts and Make targets suffice                | You need fine-grained access to `CompiledAgentConfig`    |
| Human-readable Rich output is enough                  | You compose steps (validate → compile → custom artifact) |

The CLI is a thin Typer wrapper around the same library functions. Behavior should match; prefer the API when you need return values, exception handling, or custom orchestration.

## End-to-end example

```python
from antigravity_agentkit import AgentProject, deploy, build_agent_registry_metadata
from antigravity_agentkit.deploy import load_deployment

AGENT = "examples/hello_world"
PROJECT_ID = "my-gcp-project"
LOCATION = "us-central1"

project = AgentProject.load(AGENT)
deployment = load_deployment(project.root)

# 1. Gate
project.validate(production=True)

# 2. Inspect compile output
compiled = project.compile(production=True)

# 3. Package + deployment config
deploy_summary = deploy(project, deployment, PROJECT_ID, LOCATION, dry_run=True)
print(deploy_summary["package_dir"])

# 4. Registry metadata for inventory
metadata = build_agent_registry_metadata(project, deployment)
metadata["registry"] = {"project": PROJECT_ID, "location": LOCATION}
```

For production CI patterns, continue to [Production workflows](12-production-workflows.md).

## Related guides

- [Getting started](01-getting-started.md) — CLI quick start
- [Validation and evals](08-validation-and-evals.md) — `production=True` and profiles
- [Packaging and deployment](09-packaging-and-deployment.md) — deploy helpers
- [Registry and publishing](10-registry-and-publishing.md) — metadata and skills
