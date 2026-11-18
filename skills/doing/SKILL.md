---
name: doing
description: Use when starting, continuing, or completing any task, including single-step work, or when displaying tracked work.
argument-hint: "show [all] | task <DESCRIPTION> | done [ID]"
---

# Doing

Track work that has started, not a backlog. Keep completed entries in
`~/.better-code/doing.md`; keep interrupted, blocked, failed, and unfinished work
open. Separate tasks in one session can be open at the same time.

## Automatic tracking

When starting any new task, including single-step work, record it before
beginning substantive work. The plugin's session-start and prompt-submission
hooks inject this rule independently of other Better Code skills.
Record one entry for the work being started, not its planned subtasks. A task
already recorded keeps its ID when work continues or the session resumes. When
that task is complete, mark its entry done. Never mark an incomplete task done
because the session ended or the user changed topics.

If the saved ID is unavailable when continuing or resuming, inspect
`show --json` and match the current session ID and task context before creating
an entry. Reuse an identifiable existing entry; ask when the match is ambiguous.
Repeated prompts or hook reminders do not start another entry for the same task.

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

For delegated work, also pass `--parent-session-id` with the coordinating
session's ID. Give that ID to delegates, including nested delegates, so their
entries remain recoverable by the coordinator. Record the delegate's own
`--session-id` when the host supplies it. For Claude Code subagents, use the
host-provided `agent_id` as their `--session-id`; the shared parent `session_id`
identifies the coordinator, not the child. Never invent an ID. If the delegate
continues the same task, pass the saved task ID instead of creating another entry.

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

## Completion checkpoint

Before every final response, task switch, or handoff, reconcile the task IDs
owned by this session, including delegated tasks. Use saved IDs; after a resume
or context loss, run `show --json --session-id SESSION_ID` to recover this
session's open entries and explicitly linked delegated entries. Replace
`SESSION_ID` with the host-provided session ID. Match task context before acting.
Do not reconcile unrelated sessions without an explicit request.

For each task, compare the requested deliverables with verified results:

- If every deliverable is complete, run `done ID` before reporting completion.
  A review or investigation is complete when its requested output is verified,
  even if it identifies findings. Repairs are separate work unless included in
  that task.
- If any deliverable remains partial, blocked, failed, or interrupted, keep the
  entry open. A published review, merged PR, handoff, or turn ending does not
  complete an unfinished compound task.
- If the helper fails, report the task ID and error. Distinguish a verified
  deliverable from an unconfirmed ledger update; never claim it was checked off.
  Use `show all --json` to check an uncertain update before retrying.

Delegated results must include these fields:

| Field | Required content |
| --- | --- |
| Doing ID | The saved task ID, or the tracking error if no ID was obtained. |
| Completion status | Deliverable complete or incomplete; ledger done, open, or update unconfirmed. |
| Evidence | Verification command and result, report location, or other evidence for each requested deliverable; remaining work and helper errors. |

The parent reconciles returned IDs against these results before its own final
response. A complete child review does not complete a parent task that also
requires repairs.

On hosts that run the plugin's `Stop` and `SubagentStop` hooks, an open owned
entry triggers one reconciliation reminder. The hooks read the helper's scoped
output; they never mark entries done. The `stop_hook_active` guard allows a
response with legitimately open tasks instead of repeatedly blocking it.
`SubagentStop` scopes feedback to the child's `agent_id`, not the shared parent
session. If the child's identity was unavailable when tracking started, the
coordinator still recovers its linked entry at the parent's checkpoint.
On other hosts, perform this checkpoint explicitly. A display-only request
never starts or completes entries, even if a hook reminds you about open work.

## Commands

The user can invoke `better-code:doing` with these arguments:

| Arguments | Action |
| --- | --- |
| No arguments | Display the helper's `show open` table when invoked explicitly. |
| `show` or `show open` | Display the helper's `show open` table. |
| `show all` | Display the helper's `show all` table, including completed entries. |
| `task DESCRIPTION` | Record the specified task as started, even if it is short. |
| `done` | Complete the current task. |
| `done ID` | Complete the task identified by the full ID shown in the table. |

The `show` table includes full task IDs accepted by `done ID`. Use the helper's
`show --json` to inspect session ownership as well.
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
