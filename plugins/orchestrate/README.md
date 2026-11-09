# Orchestrate: a multi-agent development cycle as a Claude Code plugin

`/orchestrate <issue-number>` runs a GitHub issue through a fixed development cycle: a Programmer works it on its own branch and opens a PR (or explains on the issue why not), a Reviewer reviews on GitHub, the two debate until the Reviewer says `LGTM`, a CI Monitor reports the checks that matter, a Verification Planner files every before-merging requirement as a tracking issue, and a Verifier carries them out.
The session that runs the skill is the **Orchestrator**: it dispatches, labels, and routes, and never does the work itself.

The plugin is self-contained: everything about the cycle lives here, and everything about the project it runs in lives in the project (its instructions and one configuration file).
That split is what lets the plugin move to other projects, or out of this one, without either side losing anything.

## Layout

| Path                           | What it is                                                                                                                                                                                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.claude-plugin/plugin.json`   | The plugin manifest.                                                                                                                                                                             |
| `skills/orchestrate/SKILL.md`  | The `/orchestrate` skill: the Orchestrator's rules, the label protocol, and the routing between rounds. Loads when the user invokes it, never on its own.                                        |
| `agents/`                      | One sub-agent per role: `programmer`, `reviewer`, `verification-planner`, `verifier`. Each runs in its own git worktree.                                                                         |
| `reference/`                   | Documents the skill and the agents read on demand, so no agent's context carries a phase it is not in.                                                                                           |
| `hooks/hooks.json`             | The plugin's hooks: the dispatch-form check on every Agent call, the `/orch-hooks` handler, and the check that keeps tool calls away from the hook state.                                        |
| `scripts/hooks/`               | The hook scripts: `check_dispatch.py`, `orchestrator_guard.py` (registered by the Orchestrator skill for the session that runs it), `hook_state.py`, `protect_state.py`, and the form validator. |
| `skills/orch-hooks/SKILL.md`   | `/orch-hooks disengage` and `/orch-hooks engage`: switch both hooks off, or back on, for the current session. User-invoked only.                                                                 |
| `scripts/ci_monitor/`          | The CI Monitor, with its README and tests.                                                                                                                                                       |
| `scripts/dispatch_cost.py`     | Reports a cycle's token spend from the session transcripts, while they exist.                                                                                                                    |
| `scripts/check_config.py`      | Validates a project configuration file, from a dot-and-tilde checkout locally or in CI (see "Project configuration").                                                                            |

Every script is standard-library Python or plain bash, with its tests in a `test_*` file beside it.

The GitHub REST helpers the cycle calls, `update_gh_labels.sh`, `link_gh_issues.py` and `delete_gh_comment.sh`, belong to the github-supplement plugin, which this plugin declares as a dependency.
Claude Code puts that plugin's `bin/` on the Bash tool's `PATH`, so the cycle runs them by bare name.

## Progressive revelation

Nothing here loads into a session on its own.
The Orchestrator skill sets `disable-model-invocation: true`, so its description is not even listed to the model; only `/orchestrate` loads it.
The skill holds the rules every phase needs and names the reference file for each later phase (`reference/ci-monitor-loop.md` once a Reviewer says `LGTM`, `reference/verification.md` once the named checks are green), so the Orchestrator reads a phase when it reaches it.
Each agent definition is its own system prompt and names the reference files its role reads (`reference/review-cycle.md` for the Author and Reviewer, `reference/nested-subagents.md` for any agent that delegates), so a Reviewer never carries the Planner's procedure and the Programmer never carries the Monitor loop.
The scripts' READMEs load only when an agent reads a file beside them.

## Communication rules

A sub-agent receives the **dispatch form** of `reference/dispatch-form.md` and nothing else: five lines naming the repository, the issue, the PR, the branch, and a verification-plan comment id, each `None` where it does not apply.
Everything else it needs is on GitHub, where it reads it fresh each round.
The Orchestrator never summarizes, interprets, or adds context, and never carries one agent's words to another; Author and Reviewer argue in PR comments.

Two hooks enforce this rather than ask for it:

- `hooks/hooks.json` runs `scripts/hooks/check_dispatch.py` before every Agent call.
  A call whose `subagent_type` is one of this plugin's agents is refused, with the reason and the form printed for the model, unless its `prompt` is exactly the form.
- The Orchestrator skill registers `scripts/hooks/orchestrator_guard.py` for the rest of the session that invoked `/orchestrate`.
  In that session's main conversation (never in a sub-agent) it refuses `Edit`, `Write` and `NotebookEdit`; allows `Read` and `Grep` only on Markdown or files under the project's `.claude/` or the plugin's directory, never under `.claude/worktrees/`; lets `Bash` and `Monitor` run only the commands the skill names (`date`, `sleep`, a few `git` subcommands, and the plugin's own scripts), with no shell operators; and refuses a `SendMessage` that is not the form.
  Those are the file and shell side of the Orchestrator's "may not" rules in executable form.
  The GitHub MCP tools are not checked, so not reading a PR's diff or comments stays a rule the Orchestrator keeps.

To switch the hooks off for a session, a person runs `/orch-hooks disengage` (`/orch-hooks engage` restores them, `/orch-hooks status` reports).
A `UserPromptExpansion` hook makes the change: Claude Code fires that event when a person types a command, never when the model invokes one, and the skill is user-invoked only besides.
The hook records the session id in `.state/disengaged-sessions` under the plugin root; both enforcing hooks read that file first and exit before doing anything for a listed session.
The file is not under `${CLAUDE_PLUGIN_DATA}` because the Orchestrator guard is a skill hook, and Claude Code gives a skill hook only `${CLAUDE_PLUGIN_ROOT}`; a plugin update moves the root and drops the state, which re-engages the hooks.
Nothing else writes the file, and `scripts/hooks/protect_state.py` refuses any Bash, Monitor, Write or Edit call, in any session or agent, whose command or path names it.
That check reads text, so it stops the obvious route rather than every route; in Orchestrator mode the guard's command allowlist covers the rest.
Setting the environment variable `ORCHESTRATE_HOOKS_DISENGAGED` to anything but empty, `0` or `false` in Claude Code's own environment disengages the hooks for every session that has it.

Each agent returns one fixed signal (the Reviewer's `LGTM` / `Changes requested` / `Cannot work`, the Verifier's three) or a plain location report, and the Orchestrator routes on that alone.

## Project configuration

The plugin reads a project's facts from `.claude/orchestrate.json` at the project root (`${CLAUDE_PROJECT_DIR}`), a JSON object with these keys.
Keys beginning with `_` are comments.

| Key                           | Required | Read by                       | Meaning                                                                                                                                                                                                                     |
| ----------------------------- | -------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `repository`                  | yes      | Orchestrator, agents, Monitor | `OWNER/REPO`. The Orchestrator passes it to the Monitor as `--repo`.                                                                                                                                                        |
| `named_checks`                | yes      | Orchestrator                  | The CI check names the cycle drives to green. A check is green when its conclusion is `success`, `neutral`, or `skipped`. Keep a merge gate that is red by design off this list.                                            |
| `verification_plan_marker`    | no       | Planner, Verifier             | One HTML comment that is the whole first line of the verification-plan comment, and how later runs find it. Default `<!-- orchestrate-verification-plan -->`. Keep a project's historical marker so old comments are found. |
| `default_model`               | no       | Orchestrator                  | The model for every role unless the user or a `c-a-<model>` / `c-r-<model>` label says otherwise. Default `opus`.                                                                                                           |
| `max_rounds`                  | no       | Orchestrator                  | Programmer / Reviewer rounds before the cycle stops and escalates. Default `4`.                                                                                                                                             |
| `ignored_check_regex`         | no       | Monitor, Reviewer             | Check names left out of the Monitor's verdict (a merge gate). Regex.                                                                                                                                                        |
| `artifact_name_regex`         | no       | Monitor                       | Which run artifacts carry per-test markers. Regex.                                                                                                                                                                          |
| `test_marker_regex`           | no       | Monitor                       | The marker that prefixes each test's JSON payload. Regex.                                                                                                                                                                   |
| `interesting_step_regex`      | no       | Monitor                       | Steps that print a line on a non-failing conclusion. Regex.                                                                                                                                                                 |
| `deferred_verdict_step_regex` | no       | Monitor                       | Steps whose own `success` is not a test verdict. Regex.                                                                                                                                                                     |

The five regex keys are the CI Monitor's own configuration; `scripts/ci_monitor/README.md` explains each, and the Monitor ignores every other key.
`scripts/check_config.py` reports a missing or malformed key.
An installed plugin's copy is in Claude Code's plugin cache, not in the project, so run it from a checkout of dot-and-tilde.
From the project root, with dot-and-tilde checked out beside the project:

```bash
python3 ../dot-and-tilde/plugins/orchestrate/scripts/check_config.py .claude/orchestrate.json
```

In CI, check out `aunger/dot-and-tilde` with `actions/checkout` (`repository: aunger/dot-and-tilde`, `path: dot-and-tilde`, and `ref` set to the commit the project's marketplace pins), then run `python3 dot-and-tilde/plugins/orchestrate/scripts/check_config.py .claude/orchestrate.json`.

## Labels

The protocol uses these labels, which the project must have:

| Label                 | Meaning                                                                                                            |
| --------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `orchestrate`         | A human marks an issue or PR ready for the cycle. Replaced by `orchestrating` at launch.                           |
| `orchestrating`       | On the issue and the PR for the whole cycle; removed when the Orchestrator concludes. A merge gate may hold on it. |
| `changes requested`   | An Author round is owed (after a `Changes requested` review, a failed named check, or a failed verification).      |
| `changes done`        | The Author returned; removed when the Reviewer returns.                                                            |
| `verification needed` | Before-merging items are open.                                                                                     |
| `verified`            | Every before-merging item is confirmed, or there were none.                                                        |
| `c-a-<model>`         | Run the Author on `<model>`.                                                                                       |
| `c-r-<model>`         | Run the Reviewer on `<model>`.                                                                                     |

Transitions are applied with github-supplement's `update_gh_labels.sh`, never with a tool that replaces the whole label set.

## What the project supplies

The agents load the project's `CLAUDE.md` or `AGENTS.md` like any sub-agent, and defer to it for everything that is the project's rather than the cycle's: how to build and test, how to write a PR description, how to write an issue or a comment, attribution footers, and dependency pinning.
The plugin repeats none of that.

## Loading

Every part of the plugin loads only when Claude Code loads the directory **as a plugin**, together with github-supplement.
No file sits at the directory's top level as `SKILL.md`, so nothing in it loads as a plain project skill, where the plugin's path variables are not set: when the plugin is not loaded, `/orchestrate` is simply not there.

Install it from a marketplace that lists both plugins:

- **dot-and-tilde's own marketplace**, for whatever is on its default branch: `claude plugin install orchestrate --marketplace aunger/dot-and-tilde`.
- **A project's own marketplace**, committed in the project, whose entries use `git-subdir` sources with a `sha` to pin both plugins to one dot-and-tilde commit. This is how a project fixes the version it runs.
  The dependency resolves in the marketplace the plugin was installed from, so that marketplace lists github-supplement too.
- **A checkout of dot-and-tilde**, for development: `--plugin-dir` or `CLAUDE_CODE_PLUGIN_DIRS` set to its `plugins/` directory loads every plugin in it for one session.

A cloud session never installs plugins a repository declares in its `.claude/settings.json`.
A project installs them instead from a script its `SessionStart` hook runs, then asks the user to run `/reload-skills`, which picks up the newly installed skills in the running session.

With the plugin loaded, the Orchestrator skill's full name is `/orchestrate:orchestrate` and `/orchestrate` invokes it unless another command already uses that name; likewise `/orchestrate:orch-hooks` and `/orch-hooks`.

## Installing in a project

1. Install this plugin and github-supplement (see "Loading" above).
2. Write `<project>/.claude/orchestrate.json` (the table above) and check it with `scripts/check_config.py`, run from a dot-and-tilde checkout as "Project configuration" describes.
3. Create the labels above.
4. Say in the project's `CLAUDE.md` or `AGENTS.md` that the cycle is started with `/orchestrate <issue>`, and keep the project's own conventions there.
   Copy github-supplement's scratchpad rule there too (its README, "Scratchpad files"): the cycle's worktree agents share one scratchpad, and no agent reads a plugin's README.

A `GITHUB_TOKEN` with write access to issues and labels must be in the environment of the session; the scripts take it from there, never from the command line.
The sessions that run the cycle need the GitHub MCP server, which the agents use for every read and write the scripts do not cover.

## Validating

From the root of dot-and-tilde:

```bash
claude plugin validate plugins/orchestrate
python3 -m unittest discover -s plugins/orchestrate/scripts -p 'test_*.py'
python3 -m unittest discover -s plugins/orchestrate/scripts/hooks -p 'test_*.py'
python3 plugins/orchestrate/scripts/ci_monitor/test_ci_monitor.py
```
