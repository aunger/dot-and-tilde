# dot-and-tilde

A Claude Code plugin marketplace of personal development tooling.

| Plugin | What it is |
| --- | --- |
| [`orchestrate`](plugins/orchestrate/README.md) | A multi-agent development cycle for GitHub issues, started with `/orchestrate <issue>`. Depends on github-supplement. |
| [`github-supplement`](plugins/github-supplement/README.md) | GitHub REST helpers the MCP tools lack, on the Bash tool's `PATH`, and `PostToolUse` hooks that fetch after sub-agents, read back GitHub writes, and keep worktree agents in their own scratchpad subdirectory. |
| [`bag-o-agents`](plugins/bag-o-agents/agents/) | General-purpose sub-agents: `deep-planner`. |

The plugins were written in [aunger/gallery-button-for-pixel-camera](https://github.com/aunger/gallery-button-for-pixel-camera) (GB4PC).
A bare issue number such as `#748` in their code and comments is a GB4PC issue, not one of this repository's; Markdown that GitHub renders spells such references out in full, as `aunger/gallery-button-for-pixel-camera#748`.

## Installing

For whatever is on the default branch:

```bash
claude plugin install orchestrate --marketplace aunger/dot-and-tilde
```

`--marketplace` adds this marketplace in the same call, and a plugin's dependencies install with it.

To pin a project to one commit, commit a marketplace in the project whose entries point here with `git-subdir` sources and a full `sha`, and install from that.
A marketplace source such as `aunger/dot-and-tilde#<ref>` takes a branch or tag but not a commit, so the pin goes on each plugin entry.
List every plugin the project installs, dependencies included, since a dependency resolves in the marketplace its dependent came from.

The plugin manifests set no `version` on purpose.
Claude Code takes a manifest's `version` before anything else and keeps an install on its cached copy until that string changes, so a pinned version would make moving the `sha` do nothing.
Without one, a `git-subdir` plugin's version is its commit.
`claude plugin validate` warns that no version is set; that warning is expected.

A cloud session does not install plugins a repository declares in its `.claude/settings.json`.
A project there installs them from a script its `SessionStart` hook runs, then the user runs `/reload-skills`.

For development, `claude --plugin-dir plugins` loads every plugin in a checkout for one session.

## Testing

From the repository root, as CI does:

```bash
for p in plugins/*/; do claude plugin validate "$p"; done
claude plugin validate .
python3 -m unittest discover -s plugins/orchestrate/scripts -p 'test_*.py'
python3 -m unittest discover -s plugins/orchestrate/scripts/hooks -p 'test_*.py'
python3 plugins/orchestrate/scripts/ci_monitor/test_ci_monitor.py
python3 -m unittest discover -s plugins/github-supplement/tests -p 'test_*.py'
for t in plugins/github-supplement/tests/test_*.sh; do bash "$t"; done
```
