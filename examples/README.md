# AgentKit examples

Runnable example agents for learning and verification. Each example sets `spec.runtime.model` to **`gemini-3.1-flash-lite`** for lower cost.

## Layout

| Directory                                    | Demonstrates                                                                                                               |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| [`hello_world/`](hello_world/)               | Minimal `agent.yaml` + `SYSTEM.md`                                                                                         |
| [`skills/`](skills/)                         | Local `SKILL.md` packages and `read_skill`                                                                                 |
| [`subagents/`](subagents/)                   | Markdown subagent delegation tools                                                                                         |
| [`mcp/`](mcp/)                               | MCP server, policies, skills, subagents, and evals (slim `agent.yaml`; skills/subagents discovered)                        |
| [`agent_platform/`](agent_platform/)         | Enterprise reference with `deployment.yaml` and ship dry-run CI (`target: agent-platform-runtime`, alias `agent-platform`) |
| [`managed_agents_api/`](managed_agents_api/) | Managed Agents API contract emission (`target: managed-agents-api`, alias `gemini-api`)                                    |
| [`python_embedding/`](python_embedding/)     | Python API tiers: governance (core), runtime (`create_agent_from_ir`), deploy emitters, Slack-style embedding pattern      |

## Prerequisites

- Python 3.10+
- `pip install antigravity-agentkit` (or `uv sync` from a repo clone)
- For live chat: `pip install 'antigravity-agentkit[antigravity]'` (or `[all]`)
- For ship dry-run: `pip install 'antigravity-agentkit[gcp]'` (or `[all]`)
- API key: set **`GEMINI_API_KEY`** or **`GOOGLE_API_KEY`**

Validation and compile work without the SDK or API key. `run` requires both.

Most examples under `examples/` are **implement-only** (validate, compile, run, eval) and omit `deployment.yaml`. The [`agent_platform/`](agent_platform/) example is the **ship-ready** Agent Platform Runtime reference: it includes `deployment.yaml` (`target: agent-platform-runtime`) and demonstrates `package`, `deploy --dry-run`, and `register` without a live platform deploy. The [`managed_agents_api/`](managed_agents_api/) example demonstrates Managed Agents API contract emission (`target: managed-agents-api`; legacy alias `gemini-api`).

Deploy target names follow [RFC 0002](../docs/rfcs/0002-spec-first-core-frozen-ir.md): canonical `agent-platform-runtime` / `managed-agents-api`, with CLI aliases `agent-platform` / `gemini-api`.

## Quick commands

From the repository root (with the package installed or `uv run`):

```bash
# Validate every example
for d in hello_world skills subagents mcp; do
  antigravity-agentkit validate "examples/$d"
done

# Compile the minimal example
antigravity-agentkit compile examples/hello_world

# Live chat (requires SDK + API key)
antigravity-agentkit run examples/hello_world --prompt "Say hello in one sentence"
```

The MCP example ships a local stdio server at [`mcp/server/clock_mcp.py`](mcp/server/clock_mcp.py). It exposes `get_utc_time` for tool-use demos.

## Repository verification

```bash
make lint
make test
./dev/test_examples.sh
```

`dev/test_examples.sh` validates and compiles all examples, runs MCP evals, and optionally runs a live hello-world chat when an API key is set.

Python embedding (no API key required for tier 1):

```bash
uv run python examples/python_embedding/tier1_governance.py
```

See [`python_embedding/README.md`](python_embedding/README.md) for Slack-bot and application integration patterns.

## Learn more

Step-by-step guides: [`docs/guides/`](../docs/guides/)
