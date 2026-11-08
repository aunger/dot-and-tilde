#!/usr/bin/env bash
# github-supplement: Claude Code PostToolUse hook: git fetch after Agent tool calls.
#
# Registered in the plugin's hooks/hooks.json under PostToolUse with a matcher
# on tool_name == "Agent".  Runs once each time a sub-agent finishes, so the
# parent session sees any commits the sub-agent pushed before it exited.
#
# Failures are non-fatal: a warning is printed but the exit code is always 0
# so the session continues even if the network is temporarily unavailable.

set -uo pipefail

# Fetch in the session's own checkout: the hook input's cwd, else the project
# directory Claude Code exports to hooks.  The script's own path is no guide,
# because it lives in the plugin, not in the project.
INPUT="$(cat)"
REPO_ROOT="$(jq -r '.cwd // empty' <<< "$INPUT" 2> /dev/null)"
REPO_ROOT="${REPO_ROOT:-${CLAUDE_PROJECT_DIR:-$PWD}}"

git -C "$REPO_ROOT" fetch --prune --quiet \
    && echo "[post-tool-use] git fetch complete" \
    || echo "[post-tool-use] warning: git fetch failed"

exit 0
