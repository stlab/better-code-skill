"""Regression tests for ledger row boundaries and storage."""

from contextlib import redirect_stderr, redirect_stdout
import errno
import io
import json
import os
from pathlib import Path
import runpy
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "doing.py"
HELPER = runpy.run_path(str(SCRIPT))


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


class LedgerSyncTests(unittest.TestCase):
    """Check synchronization and failure reporting with real ledger files."""

    def run_main(self, home, *args):
        """Invoke the CLI in process so filesystem errors can be injected."""
        stdout, stderr = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.dict(os.environ, HOME=home):
            with mock.patch.object(sys, "argv", [str(SCRIPT), *args]):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    try:
                        HELPER["main"]()
                    except SystemExit as error:
                        code = error.code
        return subprocess.CompletedProcess(args, code, stdout.getvalue(),
                                           stderr.getvalue())

    def test_writes_sync_file_then_replace_then_directory_before_success(self):
        """Sync parent and replacement metadata before acknowledging writes."""
        with tempfile.TemporaryDirectory() as home:
            events = []
            real_sync, real_replace = os.fsync, os.replace
            home_inode = os.stat(home).st_ino

            def sync(descriptor):
                """Record real syncs and reject premature acknowledgments."""
                mode = os.fstat(descriptor)
                if stat.S_ISDIR(mode.st_mode):
                    label = "home" if mode.st_ino == home_inode else "store"
                else:
                    label = "file"
                self.assertEqual(sys.stdout.getvalue(), "")
                events.append(label)
                real_sync(descriptor)

            def replace(*args, **kwargs):
                """Record the real atomic replacement."""
                events.append("replace")
                real_replace(*args, **kwargs)

            with mock.patch("os.fsync", side_effect=sync):
                with mock.patch("os.replace", side_effect=replace):
                    for description in ("First task", "Second task"):
                        events.clear()
                        result = self.run_main(home, "task", description)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        task_id = json.loads(result.stdout)["id"]
                        self.assertEqual(events,
                                         ["home", "file", "replace", "store"])
                    events.clear()
                    result = self.run_main(home, "done", task_id)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(events, ["file", "replace", "store"])
            shown = self.run_main(home, "show", "all", "--json")
            self.assertEqual(shown.returncode, 0, shown.stderr)
            rows = json.loads(shown.stdout)
            self.assertEqual(len(rows), 2)
            self.assertFalse(rows[0]["completed"])
            self.assertTrue(rows[1]["completed"])

    def test_directory_sync_failure_reports_uncertain_update_with_task_id(self):
        """Keep a replaced ledger readable and identify uncertain updates."""
        for command in ("task", "done"):
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as home:
                    first = self.run_main(home, "task", "Existing task")
                    self.assertEqual(first.returncode, 0, first.stderr)
                    first_id = json.loads(first.stdout)["id"]
                    store_inode = os.stat(Path(home) / ".better-code").st_ino
                    real_sync = os.fsync

                    def sync(descriptor):
                        """Fail only synchronization of the storage directory."""
                        mode = os.fstat(descriptor)
                        if (stat.S_ISDIR(mode.st_mode)
                                and mode.st_ino == store_inode):
                            raise OSError(errno.EIO, "simulated directory error")
                        real_sync(descriptor)

                    argument = "New task" if command == "task" else first_id
                    with mock.patch("os.fsync", side_effect=sync):
                        result = self.run_main(home, command, argument)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("may have been saved", result.stderr)
                    self.assertIn("show all --json", result.stderr)
                    self.assertIn("simulated directory error", result.stderr)
                    shown = self.run_main(home, "show", "all", "--json")
                    self.assertEqual(shown.returncode, 0, shown.stderr)
                    rows = json.loads(shown.stdout)
                    self.assertEqual(rows[0]["id"], first_id)
                    self.assertIn(rows[-1]["id"], result.stderr)
                    self.assertEqual(len(rows), 2 if command == "task" else 1)
                    self.assertEqual(rows[0]["completed"], command == "done")
                    later = self.run_main(home, "task", "Later task")
                    self.assertEqual(later.returncode, 0, later.stderr)

    def test_parent_sync_failure_can_be_retried_without_creating_a_task(self):
        """Fail before writing and sync the parent again on a later attempt."""
        with tempfile.TemporaryDirectory() as home:
            real_sync = os.fsync
            home_inode = os.stat(home).st_ino

            def sync(descriptor):
                """Fail only synchronization of the storage parent."""
                mode = os.fstat(descriptor)
                if stat.S_ISDIR(mode.st_mode) and mode.st_ino == home_inode:
                    raise OSError(errno.EIO, "simulated parent error")
                real_sync(descriptor)

            for attempt in range(2):
                with self.subTest(attempt=attempt):
                    with mock.patch("os.fsync", side_effect=sync):
                        result = self.run_main(home, "task", "Not yet saved")
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("simulated parent error", result.stderr)
                    self.assertNotIn("may have been saved", result.stderr)
                    self.assertFalse((Path(home) / ".better-code" / "doing.md").exists())
            created = self.run_main(home, "task", "Retry")
            self.assertEqual(created.returncode, 0, created.stderr)
            shown = self.run_main(home, "show", "--json")
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual([row["description"] for row in json.loads(shown.stdout)],
                             ["Retry"])

    def test_file_sync_failure_preserves_existing_ledger(self):
        """Leave the old ledger intact when syncing temporary content fails."""
        with tempfile.TemporaryDirectory() as home:
            first = self.run_main(home, "task", "Existing task")
            self.assertEqual(first.returncode, 0, first.stderr)
            ledger = Path(home) / ".better-code" / "doing.md"
            previous = ledger.read_bytes()
            real_sync = os.fsync

            def sync(descriptor):
                """Fail only file syncs, preserving real directory syncs."""
                if stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise OSError(errno.EIO, "simulated file error")
                real_sync(descriptor)

            with mock.patch("os.fsync", side_effect=sync):
                result = self.run_main(home, "task", "Unsaved task")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("simulated file error", result.stderr)
            self.assertNotIn("may have been saved", result.stderr)
            self.assertEqual(ledger.read_bytes(), previous)
            self.assertEqual(list(ledger.parent.iterdir()), [ledger])


if __name__ == "__main__":
    unittest.main()
