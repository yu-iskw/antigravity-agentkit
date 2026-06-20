#!/usr/bin/env bash
# Optional live platform integration (requires GCP_PROJECT, GCP_LOCATION, ADC).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

: "${GCP_PROJECT:?Set GCP_PROJECT}"
: "${GCP_LOCATION:?Set GCP_LOCATION}"

AGENT="${1:-examples/agent_platform}"

echo "==> validate"
uv run antigravity-agentkit validate "${AGENT}" --level full --profile dev-restricted

echo "==> package + deploy (live)"
uv run antigravity-agentkit deploy "${AGENT}" \
	--project "${GCP_PROJECT}" \
	--location "${GCP_LOCATION}"

echo "==> deploy status"
uv run antigravity-agentkit deploy "${AGENT}" \
	--project "${GCP_PROJECT}" \
	--location "${GCP_LOCATION}" \
	--status

echo "==> eval export"
uv run antigravity-agentkit eval-export "${AGENT}" \
	--output "/tmp/${AGENT//\//-}-platform-dataset.json"

echo "Live platform smoke completed (eval --mode platform requires resource-name from deploy output)."
