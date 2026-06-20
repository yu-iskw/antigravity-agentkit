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

## Post-deploy evaluation

`antigravity-agentkit eval` runs **mock-mode** governance checks in CI — it does not call Agent Platform evaluation APIs.

After your platform team deploys the `.build/` bundle to Agent Runtime:

1. Enable GenAI OpenTelemetry on the runtime (see [Agent Platform evaluation](../../docs/guides/13-agent-platform-evaluation.md)).
2. Run offline, simulated, or online evaluation via the Google Cloud console or Agent Platform SDK.
3. Seed Platform test cases from `evals/smoke.yaml` inputs (for example, “What is the current UTC time?”) until an automated exporter exists.

Full workflow and diagrams: [docs/guides/13-agent-platform-evaluation.md](../../docs/guides/13-agent-platform-evaluation.md).

## Repository verification

Runs validate, compile, eval, optional live `run` (when an API key is set), package, deploy dry-run, and register against `examples/agent_platform/`:

```bash
bash dev/test_agent_platform.sh
```

See also [Packaging and deployment](../../docs/guides/09-packaging-and-deployment.md), [Production workflows](../../docs/guides/12-production-workflows.md), and [Agent Platform evaluation](../../docs/guides/13-agent-platform-evaluation.md).
