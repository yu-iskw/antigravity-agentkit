#!/bin/bash
# Copyright 2026 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
set -Eeuo pipefail

SCRIPT_FILE="$(readlink -f "$0")"
SCRIPT_DIR="$(dirname "${SCRIPT_FILE}")"
MODULE_DIR="$(dirname "${SCRIPT_DIR}")"

cd "${MODULE_DIR}"

CLI=(uv run antigravity-agentkit)
AGENT_DIR="examples/agent_platform"
PROJECT="${AGK_GCP_PROJECT:-demo-project}"
LOCATION="${AGK_GCP_LOCATION:-us-central1}"
BUILD_DIR="${AGENT_DIR}/.build"
PACKAGE_DIR="${BUILD_DIR}/platform-assistant"
REGISTRY_META="${BUILD_DIR}/registry-metadata.json"

export AGK_GIT_SHA="${AGK_GIT_SHA:-${GITHUB_SHA:-local}}"

echo "==> validate agent_platform example"
"${CLI[@]}" validate "${AGENT_DIR}" --level full --profile prod-readonly

echo "==> compile agent_platform example"
out="/tmp/antigravity-agentkit-agent_platform-compiled.json"
"${CLI[@]}" compile "${AGENT_DIR}" --output "${out}"
echo "    wrote ${out}"

api_key="${GEMINI_API_KEY:-${GOOGLE_API_KEY-}}"
if [[ -n ${api_key} ]]; then
	echo "==> live run agent_platform example (API key detected)"
	timeout 60 "${CLI[@]}" run "${AGENT_DIR}" \
		--prompt "Say hello in one short sentence."
else
	echo "==> skip live run (set GEMINI_API_KEY or GOOGLE_API_KEY to enable)"
fi

echo "==> eval agent_platform example"
"${CLI[@]}" eval "${AGENT_DIR}"

echo "==> package agent_platform example"
"${CLI[@]}" package "${AGENT_DIR}"

if [[ -f "${PACKAGE_DIR}/metadata.json" ]]; then
	AGK_PACKAGE_DIGEST="$(
		shasum -a 256 "${PACKAGE_DIR}/metadata.json" | awk '{print $1}'
	)"
	export AGK_PACKAGE_DIGEST
fi

echo "==> deploy dry-run"
"${CLI[@]}" deploy "${AGENT_DIR}" \
	--project "${PROJECT}" \
	--location "${LOCATION}" \
	--dry-run \
	--output "${BUILD_DIR}/deployment-config.json"

echo "==> register metadata"
"${CLI[@]}" register "${AGENT_DIR}" \
	--project "${PROJECT}" \
	--location "${LOCATION}" \
	--output "${REGISTRY_META}"

if ! grep -q '"gitSha"' "${REGISTRY_META}"; then
	echo "registry metadata missing gitSha" >&2
	exit 1
fi

if [[ -n ${AGK_PACKAGE_DIGEST-} ]] && ! grep -q '"packageDigest"' "${REGISTRY_META}"; then
	echo "registry metadata missing packageDigest" >&2
	exit 1
fi

echo "==> agent_platform example OK (artifacts under ${BUILD_DIR})"
