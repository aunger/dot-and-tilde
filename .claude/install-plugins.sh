#!/usr/bin/env bash
# .claude/install-plugins.sh: enable every plugin in this checkout's marketplace
# (.claude-plugin/marketplace.json) for sessions whose project is this checkout.
#
# A cloud session does not install plugins a repository declares in its
# .claude/settings.json, so the SessionStart hook in that file runs this script
# instead. It adds this checkout as a marketplace and installs each plugin it
# lists, at local scope: Claude Code records them in .claude/settings.local.json
# (not committed), so they are enabled here and in no other project. A plugin from
# a directory marketplace loads in place from the checkout, so an edit under
# plugins/ takes effect at the next session start or /reload-plugins, with no
# update step.
#
# Idempotent: when `claude plugin list --json` already shows every plugin enabled
# for this checkout, nothing is changed. Installing also turns a plugin back on
# that was turned off for this checkout, which is the point.
#
# Stdout is one line, which the SessionStart hook passes into the session's
# context. The claude commands' own output goes to stderr.
#
# Exits non-zero at the first command that fails.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# The marketplace's name, then one plugin name per line. A while-read loop rather
# than mapfile, which bash 3.2 (macOS's /bin/bash) lacks.
NAMES=()
while IFS= read -r name; do
    NAMES+=("$name")
done < <(python3 -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    marketplace = json.load(handle)
print(marketplace["name"])
for plugin in marketplace["plugins"]:
    print(plugin["name"])
' "$REPO_ROOT/.claude-plugin/marketplace.json")
MARKETPLACE="${NAMES[0]}"
PLUGINS=("${NAMES[@]:1}")

# Reads `claude plugin list --json` on stdin. Prints each plugin (one per line)
# that is not enabled at local scope for this checkout. Only entries recorded for
# this repository root count: the list also shows other checkouts' installs.
missing_plugins() {
    python3 -c '
import json, os, sys
marketplace, root = sys.argv[1], os.path.realpath(sys.argv[2])
listed = json.load(sys.stdin)
for name in sys.argv[3:]:
    if not any(
        entry.get("id") == name + "@" + marketplace
        and entry.get("scope") == "local"
        and entry.get("enabled")
        and os.path.realpath(str(entry.get("projectPath", ""))) == root
        for entry in listed
    ):
        print(name)
' "$MARKETPLACE" "$REPO_ROOT" "${PLUGINS[@]}"
}

PENDING=()
while IFS= read -r name; do
    [[ -n "$name" ]] && PENDING+=("$name")
done < <(claude plugin list --json | missing_plugins)

if [[ ${#PENDING[@]} -eq 0 ]]; then
    echo "[install-plugins] Already enabled for this checkout: ${PLUGINS[*]}."
    exit 0
fi

# `marketplace add` re-points the marketplace name at this checkout when another
# checkout of this repository added it first.
claude plugin marketplace add "$REPO_ROOT" --scope local >&2
for plugin in "${PENDING[@]}"; do
    claude plugin install "$plugin@$MARKETPLACE" --scope local >&2
done

# Fail loudly if a plugin is still not enabled.
STILL=$(claude plugin list --json | missing_plugins | paste -sd ' ' -)
if [[ -n "$STILL" ]]; then
    echo "[install-plugins] warning: still not enabled for this checkout: $STILL" >&2
    exit 1
fi

if [[ "${CLAUDECODE:-}" == "1" ]]; then
    echo "[install-plugins] Enabled ${PENDING[*]} for this checkout. They load in this session only after /reload-skills: ask the user to run it."
else
    echo "[install-plugins] Enabled ${PENDING[*]} for this checkout. Claude Code loads them when it next starts in $REPO_ROOT."
fi
