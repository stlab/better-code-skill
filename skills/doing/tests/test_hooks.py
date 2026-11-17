"""Exercise the plugin's registered task-tracking hook commands."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "hooks" / "hooks.json"


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
            self.assertEqual(list(home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
