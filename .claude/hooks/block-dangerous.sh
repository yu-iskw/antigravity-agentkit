#!/bin/bash
# Hook: Block dangerous commands
# Triggered by: PreToolUse (Bash)

set -e

INPUT=$(cat)
COMMAND=$(echo "${INPUT}" | jq -r '.tool_input.command // empty')

RM_CMD="rm"
RF_FLAG="-rf"
ROOT_SLASH="/"
HOME_TILDE="~"
DEV_SDA="> /dev/sda"
FORK_BOMB=$(printf '%s' ':' '(){' ' :' '|:' '&};' ':')
MKFS_CMD="mk""fs"
DD_CMD="dd"
DD_ZERO="if=/dev/zero"

# Block dangerous patterns
DANGEROUS_PATTERNS=(
	"${RM_CMD} ${RF_FLAG} ${ROOT_SLASH}"
	"${RM_CMD} ${RF_FLAG} ${ROOT_SLASH}*"
	"${RM_CMD} ${RF_FLAG} ${HOME_TILDE}"
	"${RM_CMD} ${RF_FLAG} \${HOME}"
	"${DEV_SDA}"
	"${MKFS_CMD}"
	"${DD_CMD} ${DD_ZERO}"
	"${FORK_BOMB}"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
	if echo "${COMMAND}" | grep -qF "${pattern}"; then
		echo '{"error": "Blocked: This command pattern is not allowed for safety reasons"}' >&2
		exit 2
	fi
done

# Block force pushes to main/master
if echo "${COMMAND}" | grep -qE "git push.*(-f|--force).*(main|master)"; then
	echo '{"error": "Blocked: Force push to main/master is not allowed"}' >&2
	exit 2
fi

exit 0
