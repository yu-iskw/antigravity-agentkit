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
SHIP_FIXTURE="src/antigravity_agentkit/tests/fixtures/ship_agent"
PROJECT="${AGK_GCP_PROJECT:-test-project}"
LOCATION="${AGK_GCP_LOCATION:-us-central1}"
BUILD_DIR="${SHIP_FIXTURE}/.build"
PACKAGE_DIR="${BUILD_DIR}/ship-agent"
REGISTRY_META="${BUILD_DIR}/registry-metadata.json"

export AGK_GIT_SHA="${AGK_GIT_SHA:-${GITHUB_SHA:-local}}"

echo "==> validate ship fixture"
"${CLI[@]}" validate "${SHIP_FIXTURE}" --level full --profile prod-readonly

echo "==> package ship fixture"
"${CLI[@]}" package "${SHIP_FIXTURE}"

if [[ -f "${PACKAGE_DIR}/metadata.json" ]]; then
	AGK_PACKAGE_DIGEST="$(
		shasum -a 256 "${PACKAGE_DIR}/metadata.json" | awk '{print $1}'
	)"
	export AGK_PACKAGE_DIGEST
fi

echo "==> deploy dry-run"
"${CLI[@]}" deploy "${SHIP_FIXTURE}" \
	--project "${PROJECT}" \
	--location "${LOCATION}" \
	--dry-run \
	--output "${BUILD_DIR}/deployment-config.json"

echo "==> register metadata"
"${CLI[@]}" register "${SHIP_FIXTURE}" \
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

echo "==> ship fixture OK (artifacts under ${BUILD_DIR})"
