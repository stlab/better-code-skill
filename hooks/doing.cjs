/** Emits task-tracking instructions without reading prompts or writing a ledger. */
const context = [
  "Automatic Doing tracking applies to every started task, including one-step",
  "work, whether or not another Better Code skill applies.",
  "Before substantive work on a new task, invoke better-code:doing (or its",
  "installed short name, doing) and follow its automatic tracking instructions.",
  "Record one entry for the task, not one per prompt or planned subtask.",
  "Reuse the task's existing ID when continuing or resuming; repeated hook",
  "reminders do not start new tasks. Recover an existing ID before adding one.",
  "When the task is complete, mark that entry done. Leave interrupted, blocked,",
  "failed, or unfinished tasks open. Do not equate a turn ending with completion.",
  "A request only to display the Doing list does not start or complete a task.",
  "Report tracking errors rather than claiming the task was recorded.",
].join("\n");

process.stdout.write(JSON.stringify({ additionalContext: context }) + "\n");
