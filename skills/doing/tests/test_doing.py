"""Regression tests for ledger row boundaries."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "doing.py"


class LedgerRowTests(unittest.TestCase):
    """Check text round trips and malformed-row rejection through the CLI."""

    def run_doing(self, home, *args):
        """Run the helper with an isolated home and capture its output."""
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env=dict(os.environ, HOME=home),
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_line_separators_round_trip_and_allow_updates(self):
        """Preserve text separators in every cell and retain existing tasks."""
        separators = (
            "\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e",
            "\x85", "\u2028", "\u2029",
        )
        for separator in separators:
            with self.subTest(separator=ascii(separator)):
                with tempfile.TemporaryDirectory() as home:
                    first = self.run_doing(home, "task", "Existing task")
                    self.assertEqual(first.returncode, 0, first.stderr)
                    first_id = json.loads(first.stdout)["id"]
                    value = "Copied" + separator + "text"
                    created = self.run_doing(
                        home, "task", value, "--location", value,
                        "--session-name", value, "--tmux", value,
                    )
                    self.assertEqual(created.returncode, 0, created.stderr)
                    task_id = json.loads(created.stdout)["id"]
                    shown = self.run_doing(home, "show", "--json")
                    self.assertEqual(shown.returncode, 0, shown.stderr)
                    rows = json.loads(shown.stdout)
                    self.assertEqual([row["id"] for row in rows],
                                     [first_id, task_id])
                    for field in ("description", "location", "session", "tmux"):
                        self.assertEqual(rows[1][field], value)
                    completed = self.run_doing(home, "done", task_id)
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    added = self.run_doing(home, "task", "Later task")
                    self.assertEqual(added.returncode, 0, added.stderr)
                    history = self.run_doing(home, "show", "all", "--json")
                    self.assertEqual(history.returncode, 0, history.stderr)
                    rows = json.loads(history.stdout)
                    self.assertEqual(rows[0]["id"], first_id)
                    self.assertFalse(rows[0]["completed"])
                    self.assertTrue(rows[1]["completed"])
                    self.assertEqual(rows[2]["description"], "Later task")

    def test_extra_blank_row_is_rejected_without_overwriting_ledger(self):
        """Reject an extra row rather than silently ignoring malformed data."""
        with tempfile.TemporaryDirectory() as home:
            created = self.run_doing(home, "task", "Existing task")
            self.assertEqual(created.returncode, 0, created.stderr)
            ledger = Path(home) / ".better-code" / "doing.md"
            malformed = ledger.read_bytes() + b"\n"
            ledger.write_bytes(malformed)
            for args in (("show",), ("task", "Later task")):
                result = self.run_doing(home, *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Malformed ledger row", result.stderr)
                self.assertEqual(ledger.read_bytes(), malformed)

    def test_final_newline_is_optional(self):
        """Read a final row without a newline and preserve it on update."""
        with tempfile.TemporaryDirectory() as home:
            created = self.run_doing(home, "task", "Existing task")
            self.assertEqual(created.returncode, 0, created.stderr)
            task_id = json.loads(created.stdout)["id"]
            ledger = Path(home) / ".better-code" / "doing.md"
            ledger.write_bytes(ledger.read_bytes().rstrip(b"\n"))
            shown = self.run_doing(home, "show", "--json")
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual(json.loads(shown.stdout)[0]["id"], task_id)
            completed = self.run_doing(home, "done", task_id)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            history = self.run_doing(home, "show", "all", "--json")
            self.assertEqual(history.returncode, 0, history.stderr)
            self.assertTrue(json.loads(history.stdout)[0]["completed"])


if __name__ == "__main__":
    unittest.main()
