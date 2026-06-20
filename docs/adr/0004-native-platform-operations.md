# ADR 0004: Native platform operations (M3)

- **Status:** Accepted
- **Date:** 2026-06-20
- **Deciders:** antigravity-agentkit maintainers

## Context

[ADR 0003](0003-agent-platform-boundary.md) deferred Tier D (live deploy, registry apply, platform eval, observability wiring) to Agents CLI and platform teams. Enterprise users need a single toolchain from markdown-first authoring through live Agent Runtime operations without maintaining a separate ADK scaffold project.

Agents CLI remains the reference lifecycle implementation; antigravity-agentkit already emits compatible artifacts (`deployment-config.json`, source packages, registry metadata).

## Decision

**M3 brings Tier D into antigravity-agentkit** via native `vertexai` / `google-cloud-aiplatform` SDK clients—not subprocess bridges to Agents CLI.

| Capability         | M3 approach                                                                    |
| ------------------ | ------------------------------------------------------------------------------ |
| Live deploy        | `vertexai.Client().agent_engines.create/update` from IR source packages        |
| IAM / identity     | `deployment.yaml` `spec.identity` → `identity_type` + `service_account`        |
| Observability      | `spec.observability` → `env_vars` on deploy config (OTEL, BQ hints)            |
| Register / publish | Regional Agent Registry + Skill Registry REST/SDK apply                        |
| Gemini Enterprise  | Catalog publish after registry + deploy (`publish` command)                    |
| Platform eval      | `client.evals` + `eval export` from AgentKit YAML                              |
| Rollback           | `.build/.deploy/<agent>/` state + immutable revisions + `agent_engines.update` |

**Still platform-team owned (not in AgentKit):**

- Terraform / `agents-cli infra` for BQ datasets, telemetry buckets, WIF CI runners
- IAM role binding apply (AgentKit emits `iam-hints.json` sidecar only)
- Model Armor, Gateway infrastructure beyond declarative egress metadata

Tier A/B behavior is unchanged. Mock eval remains the default CI path.

## Consequences

- Authors can run end-to-end ship + deploy + register from one CLI when GCP credentials are configured.
- AgentKit maintains SDK version alignment with pre-GA Platform APIs.
- Core-only CI stays credential-free; live paths are gated by `[gcp]` extra and `@pytest.mark.gcp`.

## Alternatives considered

1. **Agents CLI subprocess bridge** — rejected; AgentKit IR packages are not ADK scaffold projects.
2. **Keep Tier D out of scope** — rejected for M3 enterprise requirement.
3. **Full Terraform in AgentKit** — rejected; duplicates Agents CLI infra; YAML declares intent only.

## Trade-offs

- Pre-GA API drift requires pinned `google-cloud-aiplatform[agent_engines]` and integration tests.
- 8MB `source_packages` Platform limit requires package size validation.
- Antigravity SDK agents need a Platform runtime adapter (`platform_adapter.py`) with explicit `class_methods`.
- Public Agent Engine create/update calls are blocking; AgentKit does not wrap private operation APIs.

## References

- [ADR 0003: Agent Platform boundary](0003-agent-platform-boundary.md)
- [Deploy an agent](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent)
- [Manage deployed agents](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/manage-deployed-agents)
- [Agents CLI lifecycle](https://google.github.io/agents-cli/guide/lifecycle/)
