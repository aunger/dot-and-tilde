#!/usr/bin/env bash
# test_post_tool_use_fetch.sh: Shell-based tests for
# the github-supplement plugin's scripts/post-tool-use-fetch.sh.
#
# The hook runs "git fetch --prune --quiet" in the session's checkout: the
# first of $CLAUDE_PROJECT_DIR and the hook input's cwd inside a work tree.
# These tests use a fake "git" on PATH to verify behaviour without
# requiring a live network or a real remote.
#
# Covers:
#   (a) Invokes git with the expected arguments (-C <repo> fetch --prune --quiet)
#   (b) Exits 0 when git fetch succeeds
#   (c) Exits 0 even when git fetch fails (offline-safe--never aborts session)
#   (d) Prints a warning line when git fetch fails
#   (e) Fetches in $CLAUDE_PROJECT_DIR, not the hook input's cwd
#   (f) Falls back to the input's cwd when $CLAUDE_PROJECT_DIR is not set
#   (g) Falls back to the input's cwd when $CLAUDE_PROJECT_DIR is not in a work tree
#   (h) Skips a git directory, where rev-parse prints "false" and exits 0
#
# Always exits 0 on success, non-zero on failure.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SCRIPT_DIR/../scripts/post-tool-use-fetch.sh"
PAYLOAD='{"tool_name":"Agent","cwd":"/work/checkout"}'

PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

# Create a temp dir for fake git binaries and a scratch git-args capture file.
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

GIT_ARGS_FILE="$TMP_DIR/git_args"

# (a) & (b) Verify git is called with expected args and hook exits 0----------
echo ""
echo "=== (a)+(b) git called with correct args; exits 0 on success ==="

# Fake git: record args, succeed.
cat > "$TMP_DIR/git" << 'EOF'
#!/usr/bin/env bash
echo "$@" >> "$GIT_ARGS_FILE"
exit 0
EOF
# GIT_ARGS_FILE must be visible inside the fake git.
export GIT_ARGS_FILE
chmod +x "$TMP_DIR/git"

OUTPUT=$(PATH="$TMP_DIR:$PATH" bash "$HOOK" <<< "$PAYLOAD" 2>&1)
EXIT_CODE=$?

RECORDED_ARGS="$(cat "$GIT_ARGS_FILE" 2>/dev/null || true)"
# Expected: "-C <some-path> fetch --prune --quiet"
if echo "$RECORDED_ARGS" | grep -qE '^-C .+ fetch --prune --quiet$'; then
    pass "(a) git called with -C <path> fetch --prune --quiet"
else
    fail "(a) unexpected git args: '$RECORDED_ARGS'"
fi

if [[ $EXIT_CODE -eq 0 ]]; then
    pass "(b) exit 0 on success"
else
    fail "(b) expected exit 0, got $EXIT_CODE"
fi

# (c) & (d) Verify hook exits 0 even when git fetch fails--------------------
echo ""
echo "=== (c)+(d) exits 0 and prints warning when git fetch fails ==="

rm -f "$GIT_ARGS_FILE"

# Fake git: succeed for non-fetch subcommands (none expected here), fail for fetch.
cat > "$TMP_DIR/git" << 'EOF'
#!/usr/bin/env bash
echo "$@" >> "$GIT_ARGS_FILE"
# Fail when called as: git -C <path> fetch ...
if [[ "$*" == *"fetch"* ]]; then
    exit 1
fi
exit 0
EOF
chmod +x "$TMP_DIR/git"

OUTPUT=$(PATH="$TMP_DIR:$PATH" bash "$HOOK" <<< "$PAYLOAD" 2>&1)
EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    pass "(c) exit 0 even when git fetch fails"
else
    fail "(c) expected exit 0 on fetch failure, got $EXIT_CODE"
fi

if echo "$OUTPUT" | grep -qi "warning"; then
    pass "(d) warning message printed on fetch failure"
else
    fail "(d) no warning message found in output: '$OUTPUT'"
fi

# (e)-(h) Where the hook fetches---------------------------------------------
echo ""
echo "=== (e)-(h) fetches in \$CLAUDE_PROJECT_DIR, else the input's cwd ==="

# Fake git: /work/not-a-repo is outside any repository and /work/repo/.git is a
# git directory (rev-parse prints "false" and exits 0); every other directory
# is a work tree.  Only fetches are recorded.
cat > "$TMP_DIR/git" << 'EOF'
#!/usr/bin/env bash
if [[ "$3" == "rev-parse" ]]; then
    case "$2" in
        /work/not-a-repo) exit 128 ;;
        /work/repo/.git) echo false; exit 0 ;;
        *) echo true; exit 0 ;;
    esac
fi
echo "$@" >> "$GIT_ARGS_FILE"
exit 0
EOF
chmod +x "$TMP_DIR/git"

# expect_fetch LABEL DIR PROJECT_DIR PAYLOAD: run the hook, check it fetched in DIR.
expect_fetch() {
    rm -f "$GIT_ARGS_FILE"
    if [[ -n "$3" ]]; then
        PATH="$TMP_DIR:$PATH" CLAUDE_PROJECT_DIR="$3" bash "$HOOK" <<< "$4" > /dev/null 2>&1
    else
        (unset CLAUDE_PROJECT_DIR; PATH="$TMP_DIR:$PATH" bash "$HOOK" <<< "$4" > /dev/null 2>&1)
    fi
    if [[ "$(cat "$GIT_ARGS_FILE" 2>/dev/null)" == "-C $2 fetch --prune --quiet" ]]; then
        pass "$1"
    else
        fail "$1: unexpected git args: '$(cat "$GIT_ARGS_FILE" 2>/dev/null)'"
    fi
}

expect_fetch "(e) fetches in \$CLAUDE_PROJECT_DIR, not the input's cwd" \
    /work/project /work/project "$PAYLOAD"
expect_fetch "(f) falls back to the input's cwd when \$CLAUDE_PROJECT_DIR is not set" \
    /work/checkout "" "$PAYLOAD"
expect_fetch "(g) falls back to the input's cwd when \$CLAUDE_PROJECT_DIR is not in a work tree" \
    /work/checkout /work/not-a-repo "$PAYLOAD"
expect_fetch "(h) skips a git directory, where rev-parse prints false" \
    /work/checkout /work/repo/.git "$PAYLOAD"

# Summary--------------------------------------------------------------------
echo ""
echo "Results: $PASS passed, $FAIL failed."
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
