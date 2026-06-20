# Python embedding examples

AgentKit is a **Python library**, not only a CLI. These scripts show how to embed declarative agents in applications (Slack bots, FastAPI services, CI jobs) using the three API tiers from [RFC 0002](../../docs/rfcs/0002-spec-first-core-frozen-ir.md).

## Layout

```text
python_embedding/
  agents/support-triage/     # Shared agent spec (no Slack-specific code)
  tier1_governance.py        # Core: validate + compile + eval (no SDK)
  tier2_runtime.py           # Runtime: create_agent_from_ir / create_agent_from_project
  tier3_deploy.py            # Deploy: build_deployment_config dry-run shape
  slack_bot_pattern.py       # Async handler pattern for Slack-style integrations
```

## Prerequisites

| Script                                     | Install                                                              | Credentials                          |
| ------------------------------------------ | -------------------------------------------------------------------- | ------------------------------------ |
| `tier1_governance.py`                      | `pip install antigravity-agentkit`                                   | None                                 |
| `tier2_runtime.py`, `slack_bot_pattern.py` | `pip install 'antigravity-agentkit[antigravity]'`                    | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| `tier3_deploy.py`                          | `pip install 'antigravity-agentkit[gcp]'` (or base + deploy in tree) | None for config emission             |

From a repo clone: `uv run python examples/python_embedding/tier1_governance.py`

## Tier 1 — governance / CI

```python
from antigravity_agentkit import AgentProject

project = AgentProject.load("./agents/support-triage")
project.validate(production=True)
ir = project.compile()
assert ir.capabilities.mode == "restricted"
```

```bash
uv run python examples/python_embedding/tier1_governance.py
```

## Tier 2 — application runtime

Prefer the stable public import path (not `antigravity_agentkit.sdk.runtime`):

```python
from antigravity_agentkit import AgentProject
from antigravity_agentkit.runtime import create_agent_from_ir

project = AgentProject.load("./agents/support-triage")
ir = project.compile(production=True)
agent = create_agent_from_ir(ir, project_root=project.root, interactive=False)
```

Or the convenience wrapper:

```python
from antigravity_agentkit.runtime import create_agent_from_project

agent = create_agent_from_project(project, production=True, interactive=False)
```

## Tier 3 — deployment emitters

```python
from antigravity_agentkit import AgentProject, build_deployment_config, load_deployment

project = AgentProject.load("./agents/support-triage")
deployment = load_deployment("./agents/support-triage")
config = build_deployment_config(
    project=project,
    deployment=deployment,
    project_id="my-project",
    location="asia-northeast1",
)
```

## Slack bot pattern

`slack_bot_pattern.py` shows an `async def handle_app_mention(event) -> str` handler you can wire to [slack-bolt](https://slack.dev/bolt-python/). AgentKit does **not** own OAuth, retries, or HTTP routing — only agent load, validation, compile, and runtime construction.

```bash
pip install 'antigravity-agentkit[antigravity]' slack-bolt
# Copy agents/support-triage/ and slack_bot_pattern.py into your bot service.
```

## Learn more

- [Python API guide](../../docs/guides/11-python-api.md)
- [Getting started](../hello_world/) — minimal agent spec
