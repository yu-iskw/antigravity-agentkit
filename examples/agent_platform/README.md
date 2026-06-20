# Platform Assistant (Agent Platform reference)

Enterprise reference agent demonstrating governed runtime authoring **and** Agent Platform ship manifests. This is the only bundled example that includes `deployment.yaml`.

Replace placeholder values in `deployment.yaml` (service account, gateway endpoints, labels) before a real platform deploy. This repository does not perform live deploys — use dry-run artifacts in CI/GitOps.

## What it demonstrates

| Layer   | Files                                                              |
| ------- | ------------------------------------------------------------------ |
| Runtime | `agent.yaml`, `SYSTEM.md`, MCP, policies, skills, subagents, evals |
| Ship    | `deployment.yaml` — scaling, service account, gateway egress       |

## Prerequisites

Same as other examples: Python 3.10+, `antigravity-agentkit`, and for live chat `antigravity-agentkit[antigravity]` plus `GEMINI_API_KEY` or `GOOGLE_API_KEY`.

## Implement lifecycle

```bash
# Development validation
antigravity-agentkit validate examples/agent_platform --level full --profile dev-open

# Compile and run locally
antigravity-agentkit compile examples/agent_platform
antigravity-agentkit run examples/agent_platform --prompt "What is the current UTC time?"

# Eval gate
antigravity-agentkit eval examples/agent_platform
```

## Ship lifecycle (dry-run only)

```bash
PROJECT="${AGK_GCP_PROJECT:-demo-project}"
LOCATION="${AGK_GCP_LOCATION:-us-central1}"

antigravity-agentkit validate examples/agent_platform \
  --level full --profile prod-readonly

antigravity-agentkit package examples/agent_platform

antigravity-agentkit deploy examples/agent_platform \
  --project "${PROJECT}" \
  --location "${LOCATION}" \
  --dry-run

antigravity-agentkit register examples/agent_platform \
  --project "${PROJECT}" \
  --location "${LOCATION}"
```

Artifacts land under `examples/agent_platform/.build/`.

## Repository verification

Runs validate, compile, eval, optional live `run` (when an API key is set), package, deploy dry-run, and register against `examples/agent_platform/`:

```bash
bash dev/test_agent_platform.sh
```

See also [Packaging and deployment](../../docs/guides/09-packaging-and-deployment.md) and [Production workflows](../../docs/guides/12-production-workflows.md).
