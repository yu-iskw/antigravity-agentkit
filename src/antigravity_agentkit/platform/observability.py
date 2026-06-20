"""Compile observability settings into Platform deploy env_vars."""

from __future__ import annotations

from antigravity_agentkit.schema.deployment import DeploymentManifest, ObservabilityConfig

_CAPTURE_CONTENT_VALUES = {
    "false": "false",
    "event_only": "EVENT_ONLY",
    "full": "true",
}


def resolve_observability(deployment: DeploymentManifest) -> ObservabilityConfig | None:
    """Return observability block when configured."""
    return deployment.spec.observability


def observability_env_vars(deployment: DeploymentManifest) -> dict[str, str]:
    """Map deployment observability spec to runtime environment variables."""
    observability = resolve_observability(deployment)
    if observability is None:
        return {}

    env_vars: dict[str, str] = {}
    if observability.cloud_trace:
        env_vars["OTEL_SEMCONV_STABILITY_OPT_IN"] = "gen_ai_latest_experimental"

    capture = _CAPTURE_CONTENT_VALUES.get(observability.capture_message_content)
    if capture is not None:
        env_vars["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = capture

    if observability.logs_bucket:
        env_vars["LOGS_BUCKET_NAME"] = observability.logs_bucket

    if observability.big_query_analytics:
        env_vars["BQ_ANALYTICS_ENABLED"] = "true"
        if observability.bq_dataset:
            env_vars["BQ_ANALYTICS_DATASET_ID"] = observability.bq_dataset

    return env_vars


def observability_requirements_extra(deployment: DeploymentManifest) -> list[str]:
    """Return additional requirements.txt lines for observability plugins."""
    observability = resolve_observability(deployment)
    if observability is None or not observability.big_query_analytics:
        return []
    return [
        "google-cloud-aiplatform[agent_engines,adk]>=1.144",
        "google-adk>=1.0",
    ]
