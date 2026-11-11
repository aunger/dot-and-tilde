# agent-citizenship

Skills for working well in a shared repository, written for any project.

| Skill | Use it when |
| --- | --- |
| [`code-edit`](skills/code-edit/SKILL.md) | Editing code: simple changes, commits split by concern, third-party pins, tests, and re-checking prose before finishing. |
| [`pr-creation`](skills/pr-creation/SKILL.md) | Deciding whether to open a pull request, and writing its title and description. |
| [`writing`](skills/writing/SKILL.md) | Writing an issue description or a comment. |

## Using them in a project

Name the skills in the project's `CLAUDE.md` or `AGENTS.md`, for the tasks they cover, for example "If creating a PR, use the `agent-citizenship:pr-creation` skill".
A session can load a skill from its description alone, but a sub-agent takes its conventions from those files and may not; orchestrate's agents, for one, follow whatever the project's `CLAUDE.md` or `AGENTS.md` names.

The skills leave out what is particular to one project, such as its build and lint commands or its prose rules, and defer to the project's own files for them.
Put those in the same `CLAUDE.md` or `AGENTS.md`.
