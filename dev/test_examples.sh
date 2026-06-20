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
EXAMPLES=(hello_world skills subagents mcp agent_platform)

echo "==> validate examples"
for name in "${EXAMPLES[@]}"; do
	path="examples/${name}"
	if [[ ${name} == "mcp" || ${name} == "agent_platform" ]]; then
		"${CLI[@]}" validate "${path}" --level full --profile dev-open
	else
		"${CLI[@]}" validate "${path}"
	fi
done

echo "==> compile examples"
for name in "${EXAMPLES[@]}"; do
	out="/tmp/antigravity-agentkit-${name}-compiled.json"
	"${CLI[@]}" compile "examples/${name}" --output "${out}"
	echo "    wrote ${out}"
done

echo "==> eval mcp and agent_platform examples"
"${CLI[@]}" eval examples/mcp
"${CLI[@]}" eval examples/agent_platform

api_key="${GEMINI_API_KEY:-${GOOGLE_API_KEY-}}"
if [[ -n ${api_key} ]]; then
	echo "==> live run examples (API key detected)"
	LIVE_PROMPTS=(
		"hello_world|Reply with exactly: hello from agentkit"
		"skills|Use greeting-helper: run bash scripts/greet.sh Ada and reply with only the script stdout."
		"subagents|Say hello in one short sentence."
		"mcp|Say hello in one short sentence."
		"agent_platform|Say hello in one short sentence."
	)
	for entry in "${LIVE_PROMPTS[@]}"; do
		name="${entry%%|*}"
		prompt="${entry#*|}"
		echo "    run examples/${name}"
		timeout 60 "${CLI[@]}" run "examples/${name}" --prompt "${prompt}"
	done
else
	echo "==> skip live run (set GEMINI_API_KEY or GOOGLE_API_KEY to enable)"
fi

echo "==> examples OK"
