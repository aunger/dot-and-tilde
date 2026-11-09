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

# Fetch in the session's own checkout: the first of the hook input's cwd, the
# project directory Claude Code exports to hooks, and $PWD that is inside a
# git work tree.  The cwd comes first because it is where the session is
# working, but it can be a scratchpad or other directory outside any checkout,
# and then the project directory is the one to fetch.  The script's own path is
# no guide, because it lives in the plugin, not in the project.
INPUT="$(cat)"
CWD="$(jq -r '.cwd // empty' <<< "$INPUT" 2> /dev/null)"
REPO_ROOT=""
for candidate in "$CWD" "${CLAUDE_PROJECT_DIR:-}" "$PWD"; do
    [[ -n "$candidate" ]] || continue
    if git -C "$candidate" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        REPO_ROOT="$candidate"
        break
    fi
done
# With no work tree among them, try the first anyway, so the warning below says
# the fetch failed rather than the hook staying silent.
REPO_ROOT="${REPO_ROOT:-${CWD:-${CLAUDE_PROJECT_DIR:-$PWD}}}"

git -C "$REPO_ROOT" fetch --prune --quiet \
    && echo "[post-tool-use] git fetch complete" \
    || echo "[post-tool-use] warning: git fetch failed"

exit 0
