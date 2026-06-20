# ADR 0003: Agent Platform boundary for antigravity-agentkit

- **Status:** Accepted
- **Date:** 2026-06-20
- **Deciders:** antigravity-agentkit maintainers

## Context

Google Cloud Gemini Enterprise Agent Platform provides Agent Runtime, Skill Registry, Agent Registry, Agent Gateway, Sessions, Memory Bank, Sandbox, governance policies, and observability. antigravity-agentkit authors want markdown-first agents (skills, subagents, MCP, policies) and a path to ship them to Google Cloud without turning AgentKit into a second platform control plane.

## Decision

AgentKit supports Agent Platform through **four tiers**:

| Tier                      | AgentKit role                                                                                                                          | Examples                                                           |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| **A — Compile**           | Validate and compile authoring files into Antigravity SDK config                                                                       | skills, subagents, MCP, policies, capabilities, evals              |
| **B — Emit contracts**    | Write local artifacts for CI/GitOps; no GCP API calls                                                                                  | `deployment-config.json`, registry metadata JSON, skill zip        |
| **C — Platform bindings** | _Deferred (M4+)_ — optional declarative hooks compiled to SDK integration                                                              | memory, sessions, sandbox tools                                    |
| **D — Platform ops**      | _Out of scope_ — owned by platform team and [Agents CLI](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime) | live deploy, IAM policies, Gateway setup, Model Armor, online eval |

**Implement** commands (`validate`, `compile`, `run`, `eval`) do not require `deployment.yaml`. **Ship** commands (`package`, `deploy`, `register`, `publish-skill`) require it and produce Tier B artifacts only.

Live `deploy()` without `--dry-run` raises `DeployError` until a future milestone explicitly adds Agent Runtime apply. `register` and `publish-skill` never call Skill Registry or Agent Registry APIs in M2.

## Consequences

- Authors get Claude/Cursor-like DX locally; platform teams consume stable JSON/zip contracts in CI.
- AgentKit avoids duplicating Agents CLI, Terraform, and console governance workflows.
- Tier C schema hints (`spec.registry`, remote subagents) may exist in `agent.yaml` as **intent metadata** until M3/M4 wiring lands.

## Alternatives considered

1. **Full platform client in AgentKit** — rejected; overlaps Agents CLI and increases maintenance.
2. **Markdown-only, no ship artifacts** — rejected; enterprise needs reproducible deploy contracts.
3. **Implement all platform services in AgentKit** — rejected per [RFC 0001 non-goals](../rfcs/0001-declarative-antigravity-agentkit.md#32-non-goals).

## Trade-offs

- Extra CI step to apply artifacts to Agent Runtime (platform team responsibility).
- Tier C features wait for stable SDK helpers rather than premature YAML surface area.

## References

- [RFC 0001: Declarative Antigravity AgentKit](../rfcs/0001-declarative-antigravity-agentkit.md)
- [Packaging and deployment](../guides/09-packaging-and-deployment.md)
- [Production workflows](../guides/12-production-workflows.md)
- [Registry and publishing](../guides/10-registry-and-publishing.md)
