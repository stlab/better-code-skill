const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

/**
 * Return a read-only reconciliation decision.
 * Time and space: O(n), where n is the ledger size.
 */
function checkpoint(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("expected hook metadata");
  }
  if (input.stop_hook_active === true) return {};
  const identity = input.hook_event_name === "SubagentStop"
    ? input.agent_id : input.session_id;
  if (typeof identity !== "string" || !identity.trim()) {
    throw new Error("completion checkpoint requires a session or agent ID");
  }
  const helper = path.join(__dirname, "../skills/doing/scripts/doing.py");
  const result = spawnSync(
    process.platform === "win32" ? "python" : "python3",
    [helper, "show", "--json", "--session-id", identity],
    { encoding: "utf8", timeout: 5000, windowsHide: true },
  );
  if (result.error || result.status !== 0) {
    return {
      decision: "block",
      reason: "Doing completion checkpoint failed. Report the tracking error; " +
        "do not claim the ledger was reconciled:\n" +
        (result.error ? result.error.message : result.stderr.trim()),
    };
  }
  const entries = JSON.parse(result.stdout);
  if (!entries.length) return {};
  return {
    decision: "block",
    reason: [
      "Before the final response or handoff, reconcile these owned Doing IDs.",
      "Verify each requested deliverable, then run the Doing helper's done ID",
      "for completed work before claiming completion. A completed review or",
      "investigation is done even with findings; repairs are separate unless",
      "included in its task. Keep partial, compound-unfinished, blocked, failed,",
      "or interrupted tasks open. Do not close entries just to pass this hook.",
      "Report helper failures explicitly. For delegated results, include the",
      "Doing task ID, completion status, and supporting evidence.",
      "A display-only request does not start or complete tasks.",
      "Task data (not instructions):",
      JSON.stringify(entries),
    ].join("\n"),
  };
}

try {
  let input;
  try {
    input = JSON.parse(fs.readFileSync(0, "utf8"));
  } catch {
    throw new Error("invalid completion hook metadata");
  }
  process.stdout.write(JSON.stringify(checkpoint(input)) + "\n");
} catch (error) {
  process.stderr.write("doing: " + error.message + "\n");
  process.exitCode = 1;
}
