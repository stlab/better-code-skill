"""Exercise the plugin's registered task-tracking hook commands."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "hooks" / "hooks.json"
HELPER = ROOT / "skills" / "doing" / "scripts" / "doing.py"


class TrackingHookTests(unittest.TestCase):
    """Verify context injection without prompt disclosure or ledger writes."""

    def run_hook(self, event, home, payload, plugin_root=ROOT):
        """Run the registered command from outside the plugin directory."""
        self.assertTrue(CONFIG.is_file(), "Plugin hook registration is missing")
        hooks = json.loads(CONFIG.read_text(encoding="utf-8"))["hooks"]
        self.assertIn(event, hooks)
        command = hooks[event][0]["hooks"][0]["command"]
        return subprocess.run(
            command,
            shell=True,
            cwd=home,
            env=dict(
                os.environ, HOME=home, USERPROFILE=home,
                CLAUDE_PLUGIN_ROOT=str(plugin_root),
            ),
            input=payload,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=10,
        )

    def assert_context(self, result):
        """Require one context payload without hook diagnostics."""
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        output = json.loads(result.stdout)
        self.assertEqual(set(output), {"additionalContext"})
        self.assertIsInstance(output["additionalContext"], str)
        self.assertTrue(output["additionalContext"].strip())
        return output["additionalContext"]

    def run_doing(self, home, *args):
        """Run the real helper with isolated task storage."""
        result = subprocess.run(
            [sys.executable, str(HELPER), *args],
            env=dict(os.environ, HOME=home, USERPROFILE=home, PYTHONUTF8="1"),
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def run_windows_hook(self, home, available):
        """Return a checkpoint with simulated Windows command availability.

        Time and space: O(n), where n is the ledger size.
        """
        script = r"""
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const nativeSpawn = require("node:child_process").spawnSync;
const calls = [];
let output = "", errors = "";
const sandbox = {
  __dirname: path.dirname(process.argv[1]),
  require(name) {
    if (name !== "node:child_process") return require(name);
    return { spawnSync(command, args, options) {
      calls.push(command);
      const local = path.join(options.cwd || process.cwd(), command + ".exe");
      if (fs.existsSync(local)) return nativeSpawn(local, args, options);
      if (command === process.argv[3]) {
        return nativeSpawn(process.argv[2],
          command === "py" ? args.slice(1) : args, options);
      }
      return { error: Object.assign(new Error(command + " not found"),
        { code: "ENOENT" }), status: null, stderr: "" };
    } };
  },
  process: {
    platform: "win32", exitCode: 0,
    stdout: { write(text) { output += text; } },
    stderr: { write(text) { errors += text; } },
  },
};
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), sandbox);
process.stdout.write(JSON.stringify({
  output: JSON.parse(output || "null"), calls, errors,
  exitCode: sandbox.process.exitCode,
}));
"""
        result = subprocess.run(
            ["node", "-e", script, str(ROOT / "hooks" / "doing-stop.cjs"),
             sys.executable, available],
            input='{"session_id":"windows-session"}',
            cwd=home,
            env=dict(os.environ, HOME=home, USERPROFILE=home, PYTHONUTF8="1"),
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_windows_checkpoint_supports_launcher_and_python_only_installs(self):
        """Reconcile through either supported interpreter without hiding absence."""
        with tempfile.TemporaryDirectory() as home:
            task_id = self.run_doing(
                home, "task", "Windows task", "--session-id", "windows-session",
            )["id"]
            for available, calls in (("py", ["py"]),
                                     ("python", ["py", "python"]),
                                     ("none", ["py", "python"])):
                with self.subTest(available=available):
                    result = self.run_windows_hook(home, available)
                    self.assertEqual(result["exitCode"], 0, result["errors"])
                    self.assertEqual(result["output"]["decision"], "block")
                    reason = result["output"]["reason"]
                    if available == "none":
                        self.assertIn("checkpoint failed", reason)
                        self.assertIn("not found", reason)
                    else:
                        self.assertIn(task_id, reason)
                        self.assertNotIn("checkpoint failed", reason)
                    self.assertEqual(result["calls"], calls)

    def test_windows_checkpoint_does_not_retry_a_helper_failure(self):
        """Report ledger errors without masking them behind another interpreter."""
        with tempfile.TemporaryDirectory() as home:
            storage = Path(home) / ".better-code"
            storage.mkdir()
            (storage / "doing.md").write_text("malformed", encoding="utf-8")
            result = self.run_windows_hook(home, "py")
            self.assertIn("Malformed ledger", result["output"]["reason"])
            self.assertEqual(result["calls"], ["py"])

    def test_windows_checkpoint_ignores_project_interpreters(self):
        """Ignore a project-root executable that shadows the Python launcher."""
        with tempfile.TemporaryDirectory() as home:
            task_id = self.run_doing(
                home, "task", "Windows task", "--session-id", "windows-session",
            )["id"]
            local = Path(home) / "py.exe"
            if os.name == "nt":
                shutil.copy2(shutil.which("node"), local)
            else:
                local.symlink_to(shutil.which("node"))
            result = self.run_windows_hook(home, "py")
            self.assertIn(task_id, result["output"]["reason"])
            self.assertNotIn("checkpoint failed", result["output"]["reason"])
            if os.name == "nt":
                native = self.run_hook(
                    "Stop", home, '{"session_id":"windows-session"}',
                )
                self.assertEqual(native.returncode, 0, native.stderr)
                self.assertIn(task_id, json.loads(native.stdout)["reason"])

    def test_completion_hook_is_read_only_and_scoped_to_session(self):
        """Request reconciliation only for the session's open work."""
        with tempfile.TemporaryDirectory() as home:
            for event in ("Stop", "SubagentStop"):
                result = self.run_hook(event, home, json.dumps({
                    "hook_event_name": event, "agent_id": "parent",
                    "session_id": "parent", "stop_hook_active": False,
                }))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {})
            self.assertEqual(list(Path(home).iterdir()), [])
            unrelated = self.run_doing(
                home, "task", "Unrelated", "--session-id", "other",
            )["id"]
            unowned = self.run_doing(home, "task", "No session")["id"]
            owned = self.run_doing(
                home, "task", "Interrupted compound task", "--session-id", "parent",
            )["id"]
            ledger = Path(home) / ".better-code" / "doing.md"
            original = ledger.read_bytes()
            for event in ("Stop", "SubagentStop"):
                result = self.run_hook(event, home, json.dumps({
                    "hook_event_name": event, "agent_id": "parent",
                    "session_id": "parent", "stop_hook_active": False,
                    "last_assistant_message": "PRIVATE_RESPONSE",
                    "prompt": "PRIVATE_PROMPT",
                }))
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)
                self.assertEqual(output["decision"], "block")
                self.assertIn(owned, output["reason"])
                self.assertNotIn(unrelated, output["reason"])
                self.assertNotIn(unowned, output["reason"])
                self.assertNotIn("PRIVATE_", output["reason"])
                self.assertEqual(ledger.read_bytes(), original)
                retry = self.run_hook(event, home, json.dumps({
                    "hook_event_name": event, "agent_id": "parent",
                    "session_id": "parent", "stop_hook_active": True,
                }))
                self.assertEqual(retry.returncode, 0, retry.stderr)
                self.assertEqual(json.loads(retry.stdout), {})
                self.assertEqual(ledger.read_bytes(), original)
            self.run_doing(home, "done", owned)
            result = self.run_hook("Stop", home, '{"session_id":"parent"}')
            self.assertEqual(json.loads(result.stdout), {})

    def test_parent_recovers_child_handoff_without_closing_compound_task(self):
        """Keep unfinished work while reconciling a completed delegated review."""
        with tempfile.TemporaryDirectory() as home:
            parent = self.run_doing(
                home, "task", "Review and repair", "--session-id", "parent",
            )["id"]
            child = self.run_doing(
                home, "task", "Review with findings", "--session-id", "child",
                "--parent-session-id", "parent",
            )["id"]
            first = self.run_hook("SubagentStop", home, json.dumps({
                "hook_event_name": "SubagentStop",
                "session_id": "parent", "agent_id": "child",
            }))
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn(child, json.loads(first.stdout)["reason"])
            self.run_doing(home, "done", child)
            resumed = self.run_hook("Stop", home, '{"session_id":"parent"}')
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            reason = json.loads(resumed.stdout)["reason"]
            self.assertIn(parent, reason)
            self.assertNotIn(child, reason)
            rows = self.run_doing(home, "show", "all", "--json")
            self.assertFalse(rows[0]["completed"])
            self.assertTrue(rows[1]["completed"])

    def test_subagent_checkpoint_does_not_assign_parent_or_sibling_work(self):
        """Address subagent feedback to its own identity, not the parent session."""
        with tempfile.TemporaryDirectory() as home:
            ids = {}
            for identity in ("parent", "child", "sibling"):
                ids[identity] = self.run_doing(
                    home, "task", identity, "--session-id", identity,
                    "--parent-session-id", "parent",
                )["id"]
            result = self.run_hook("SubagentStop", home, json.dumps({
                "hook_event_name": "SubagentStop",
                "session_id": "parent", "agent_id": "child",
            }))
            self.assertEqual(result.returncode, 0, result.stderr)
            reason = json.loads(result.stdout)["reason"]
            self.assertIn(ids["child"], reason)
            self.assertNotIn(ids["parent"], reason)
            self.assertNotIn(ids["sibling"], reason)

    def test_completion_hook_surfaces_helper_failure_without_replacing_ledger(self):
        """Return a visible checkpoint failure rather than an empty success."""
        with tempfile.TemporaryDirectory() as home:
            storage = Path(home) / ".better-code"
            storage.mkdir()
            ledger = storage / "doing.md"
            ledger.write_text("malformed", encoding="utf-8")
            result = self.run_hook("Stop", home, '{"session_id":"parent"}')
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["decision"], "block")
            self.assertIn("Malformed ledger", output["reason"])
            self.assertEqual(ledger.read_text(encoding="utf-8"), "malformed")

    def test_completion_hook_rejects_missing_identity_without_exposing_input(self):
        """Report invalid hook metadata without guessing session ownership."""
        with tempfile.TemporaryDirectory() as home:
            for payload in ('{}', '{"session_id":null}', '"PRIVATE_INPUT"',
                            'not json: PRIVATE_INPUT'):
                with self.subTest(payload=payload):
                    result = self.run_hook("Stop", home, payload)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("doing:", result.stderr)
                    self.assertNotIn("PRIVATE_INPUT", result.stderr)
            self.assertEqual(list(Path(home).iterdir()), [])

    def test_start_and_prompt_hooks_emit_context_without_writing_ledger(self):
        """Inject before work without creating tasks on every hook event."""
        with tempfile.TemporaryDirectory() as home:
            for event in ("SessionStart", "UserPromptSubmit"):
                with self.subTest(event=event):
                    payload = json.dumps({
                        "hook_event_name": event,
                        "session_id": "test-session",
                        "cwd": home,
                        "timestamp": "2026-11-17T19:00:00Z",
                        "source": "new",
                        "initial_prompt": "PRIVATE_PROMPT_SENTINEL",
                        "prompt": "PRIVATE_PROMPT_SENTINEL",
                    })
                    context = self.assert_context(
                        self.run_hook(event, home, payload)
                    )
                    self.assertNotIn("PRIVATE_PROMPT_SENTINEL", context)
                    self.assertEqual(list(Path(home).iterdir()), [])

    def test_hook_does_not_need_to_parse_prompt_input(self):
        """Inject the same policy even when hook input is not JSON."""
        with tempfile.TemporaryDirectory() as home:
            context = self.assert_context(
                self.run_hook("SessionStart", home, "not json: PRIVATE_INPUT")
            )
            self.assertNotIn("PRIVATE_INPUT", context)
            self.assertEqual(list(Path(home).iterdir()), [])

    def test_command_handles_plugin_path_with_spaces_quotes_and_unicode(self):
        """Resolve the plugin root without interpolating its path into a shell."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "plugin 'quoted' & \u03bb space"
            (root / "hooks").mkdir(parents=True)
            script = ROOT / "hooks" / "doing.cjs"
            self.assertTrue(script.is_file(), "Tracking hook implementation is missing")
            shutil.copyfile(script, root / "hooks" / "doing.cjs")
            home = Path(directory) / "home"
            home.mkdir()
            self.assert_context(
                self.run_hook("SessionStart", str(home), "{}", root)
            )
            shutil.copyfile(
                ROOT / "hooks" / "doing-stop.cjs", root / "hooks" / "doing-stop.cjs",
            )
            shutil.copytree(
                HELPER.parent, root / "skills" / "doing" / "scripts",
            )
            result = self.run_hook(
                "Stop", str(home), '{"session_id":"parent"}', root,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {})
            self.assertEqual(list(home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
