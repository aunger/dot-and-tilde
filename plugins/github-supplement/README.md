# GitHub supplement

Tools for agents that work on GitHub through the GitHub MCP server, covering what the server's tools leave out.

## Helpers on `PATH`

Claude Code adds this plugin's `bin/` to the Bash tool's `PATH`, so each helper runs by bare name.
Each takes its token from `GITHUB_TOKEN` in the environment, never from the command line, and needs no `gh` CLI.

| Command | What it does |
| --- | --- |
| `update_gh_labels.sh OWNER REPO NUMBER [--add L]... [--remove L]...` | Adds and removes specific labels through GitHub's delta endpoints. The MCP tool's `labels` field replaces the whole set, which silently discards labels anyone else applied since it was read. |
| `link_gh_issues.py add OWNER REPO NUMBER (--blocked-by N \| --parent-of N)` | Records an issue dependency or a sub-issue. |
| `delete_gh_comment.sh OWNER REPO COMMENT_ID` | Deletes one issue or PR comment, which the MCP tools have no verb for. |

Each script's header documents its arguments and exit codes.

## Hooks

`hooks/hooks.json` registers three `PostToolUse` hooks, active in every session where the plugin is enabled:

| Matcher | Script | What it does |
| --- | --- | --- |
| `Agent` | `scripts/post-tool-use-fetch.sh` | Runs `git fetch --prune` in the session's checkout after each sub-agent returns, so the session sees what the sub-agent pushed. Never fails the call. |
| `mcp__github__.*` | `scripts/post-tool-use-github-readback.sh` | Reads back the text of every GitHub write and reports any difference from what was sent, or that it could not check. `scripts/verify_github_write.py` does the work. |
| `Bash\|Write\|Edit\|NotebookEdit` | `scripts/post-tool-use-scratchpad-isolation.sh` | Warns a worktree sub-agent that reached the shared scratchpad outside its own subdirectory (see below). |

### Scratchpad files

Every agent in a session, including each worktree sub-agent, is given the same scratchpad directory.
A helper left at its top level can be overwritten or run by another agent, which then reports results from a tree it never touched.

- Keep scratch files in a subdirectory of the scratchpad named after your worktree directory (`agent-<id>`), or for the top-level agent, the checkout directory, never at its top level.
- A helper that reports a test result prints the worktree path and `HEAD` it ran against, and you check both before reporting.

The second point is what catches a crossed result; the first only makes one rarer.
The scratchpad hook warns about the first, after the call has run, and nothing checks the second.

No agent reads this README, so a project that installs the plugin copies the two points above into its own `CLAUDE.md` or `AGENTS.md`, which every agent loads before it acts.

## Testing

From the root of dot-and-tilde:

```bash
python3 -m unittest discover -s plugins/github-supplement/tests -p 'test_*.py'
for t in plugins/github-supplement/tests/test_*.sh; do bash "$t"; done
```
