---
name: doing
description: "Commands: show [all] | task <DESCRIPTION> | done. Use when tracking started or completing multistep work."
argument-hint: "show [all] | task <DESCRIPTION> | done"
---

# Doing

Track work that has started, not a backlog. Keep completed entries in
`~/.better-code/doing.md`; keep interrupted, blocked, failed, and unfinished work
open. Separate tasks in one session can be open at the same time.

## Automatic tracking

When starting a new multistep task, record it before beginning substantive work.
Record one entry for the work being started, not its planned subtasks. A task
already recorded keeps its ID when work continues or the session resumes. When
that task is complete, mark its entry done. Never mark an incomplete task done
because the session ended or the user changed topics.

Use the bundled helper for all reads and changes; never edit the table directly.
Run `scripts/doing.py` with Python 3 relative to this skill's installed directory,
not the current working directory. Use `python3` on POSIX; on native Windows,
use `py -3` or a `python` command verified to run Python 3. If the helper,
Python 3, or ledger access is unavailable, report the error; don't claim the
work was tracked.

To start, run `task DESCRIPTION` with the available metadata options:
`--location`, `--session-name`, `--session-id`, and `--tmux`. Pass each value as
one argument. Record a concise description without secrets. Save the returned
task ID in the session context; it identifies this entry even if the session is
renamed or other work starts.

Use the repository being worked on for location. The host's current repository
identity applies only when it is the target of the work; use the relevant
working directory if no repository identity is available. For Copilot, the
host may supply a current session folder or ID. Only if it does, read that
session's `workspace.yaml` for its ID and name. If it doesn't, use only session
metadata the host provides directly. Don't search other sessions or transcripts.
Use other hosts' session metadata when explicitly provided. If a value is
unavailable, omit its option; don't guess.

For tmux, use `tmux display-message -p -t "$TMUX_PANE" '#S'` only when both
`TMUX` and `TMUX_PANE` are set. If the command fails or the pane isn't available,
omit `--tmux`; don't infer a session from the repository name.

## Commands

The user can invoke `better-code:doing` with these arguments:

| Arguments | Action |
| --- | --- |
| No arguments | Display the helper's `show open` table when invoked explicitly. |
| `show` or `show open` | Display the helper's `show open` table. |
| `show all` | Display the helper's `show all` table, including completed entries. |
| `task DESCRIPTION` | Record the specified task as started, even if it is short. |
| `done` | Complete the current task. |

Use the helper's `show --json` to inspect task IDs and session IDs when needed.
For `done`, use the current task's saved ID. If it is unavailable, match the
current session ID and task context against open entries. When exactly one entry
is identifiable, pass its ID to `done ID`. If no entry or more than one entry
could be current, use the host's question tool to ask which task the user
finished, listing the candidate descriptions. Wait for the answer before
updating. If the host has no question tool, ask in the reply. Never pick by row
order, location, or tmux name alone. An absent session ID is not a shared
identity.

Don't start or complete an entry merely because the user asked to show the list.
If the helper reports malformed data or another error, report it and leave the
file untouched rather than replacing it.

## Common mistakes

| Mistake | Correction |
| --- | --- |
| Assume a task was tracked without a returned ID | Report the tracking error. |
| Mark interrupted work complete | Leave the task open. |
| Select an ambiguous task by position or location | Ask the user which task finished. |
