# AgentKit examples

Runnable example agents for learning and verification. Each example sets `spec.runtime.model` to **`gemini-3.1-flash-lite`** for lower cost.

## Layout

| Directory                            | Demonstrates                                                    |
| ------------------------------------ | --------------------------------------------------------------- |
| [`hello_world/`](hello_world/)       | Minimal `agent.yaml` + `SYSTEM.md`                              |
| [`skills/`](skills/)                 | Local `SKILL.md` packages and `read_skill`                      |
| [`subagents/`](subagents/)           | Markdown subagent delegation tools                              |
| [`mcp/`](mcp/)                       | MCP server, policies, skills, subagents, and evals              |
| [`agent_platform/`](agent_platform/) | Enterprise reference with `deployment.yaml` and ship dry-run CI |

## Prerequisites

- Python 3.10+
- `pip install antigravity-agentkit` (or `uv sync` from a repo clone)
- For live chat: `pip install 'antigravity-agentkit[antigravity]'`
- API key: set **`GEMINI_API_KEY`** or **`GOOGLE_API_KEY`**

Validation and compile work without the SDK or API key. `run` requires both.

Most examples under `examples/` are **implement-only** (validate, compile, run, eval) and omit `deployment.yaml`. The [`agent_platform/`](agent_platform/) example is the **ship-ready** reference: it includes `deployment.yaml` and demonstrates `package`, `deploy --dry-run`, and `register` without a live platform deploy.

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

## Learn more

Step-by-step guides: [`docs/guides/`](../docs/guides/)
