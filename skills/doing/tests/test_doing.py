"""Regression tests for ledger row boundaries and storage."""

from contextlib import redirect_stderr, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
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
with mock.patch.object(sys, "path", [str(SCRIPT.parent), *sys.path]):
    HELPER = runpy.run_path(str(SCRIPT))


def link_directory(link, target):
    """Create a directory symlink or an unprivileged Windows junction."""
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True, timeout=10, check=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


class LedgerRowTests(unittest.TestCase):
    """Check text round trips and malformed-row rejection through the CLI."""

    def run_doing(self, home, *args):
        """Run the helper with an isolated home and capture its output."""
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env=dict(os.environ, HOME=home, USERPROFILE=home, PYTHONUTF8="1"),
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_displayed_ids_can_complete_the_selected_task(self):
        """Expose stable IDs without exposing hidden session metadata."""
        with tempfile.TemporaryDirectory() as home:
            ids = []
            for description in ("First task", "Second task"):
                created = self.run_doing(home, "task", description)
                self.assertEqual(created.returncode, 0, created.stderr)
                ids.append(json.loads(created.stdout)["id"])
            shown = self.run_doing(home, "show")
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertIn("| ID |", shown.stdout)
            displayed_ids = [
                line.split("|")[1].strip()
                for line in shown.stdout.splitlines()[2:]
            ]
            self.assertEqual(displayed_ids, ids)
            self.assertNotIn("<!--", shown.stdout)
            completed = self.run_doing(home, "done", displayed_ids[1])
            self.assertEqual(completed.returncode, 0, completed.stderr)
            shown = self.run_doing(home, "show")
            self.assertIn(ids[0], shown.stdout)
            self.assertNotIn(ids[1], shown.stdout)
            history = self.run_doing(home, "show", "all")
            self.assertIn(ids[1], history.stdout)
            self.assertIn("[x] Second task", history.stdout)

    def test_resumed_session_recovers_owned_and_delegated_tasks(self):
        """Recover persisted ownership without including unrelated sessions."""
        with tempfile.TemporaryDirectory() as home:
            owned = self.run_doing(
                home, "task", "Compound task", "--session-id", "parent",
            )
            self.assertEqual(owned.returncode, 0, owned.stderr)
            child = self.run_doing(
                home, "task", "Review with findings", "--session-id", "child",
                "--parent-session-id", "parent",
            )
            self.assertEqual(child.returncode, 0, child.stderr)
            unrelated = self.run_doing(
                home, "task", "Unrelated task", "--session-id", "other",
            )
            self.assertEqual(unrelated.returncode, 0, unrelated.stderr)
            owned_id = json.loads(owned.stdout)["id"]
            child_id = json.loads(child.stdout)["id"]
            recovered = self.run_doing(
                home, "show", "--json", "--session-id", "parent",
            )
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            rows = json.loads(recovered.stdout)
            self.assertEqual([row["id"] for row in rows], [owned_id, child_id])
            self.assertIsNone(rows[0]["parent_session_id"])
            self.assertEqual(rows[1]["parent_session_id"], "parent")
            completed = self.run_doing(home, "done", child_id)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            remaining = self.run_doing(
                home, "show", "--json", "--session-id", "parent",
            )
            self.assertEqual(json.loads(remaining.stdout)[0]["id"], owned_id)
            self.assertEqual(len(json.loads(remaining.stdout)), 1)
            all_rows = self.run_doing(home, "show", "all", "--json")
            self.assertEqual(len(json.loads(all_rows.stdout)), 3)
            self.assertFalse(json.loads(all_rows.stdout)[2]["completed"])

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

    def test_concurrent_writers_preserve_every_task(self):
        """Serialize concurrent writes without losing entries."""
        with tempfile.TemporaryDirectory() as home:
            descriptions = [f"Concurrent task {index}" for index in range(16)]
            with ThreadPoolExecutor(max_workers=16) as pool:
                futures = []
                for text in descriptions:
                    futures.append(pool.submit(self.run_doing, home, "task", text))
                    futures.append(pool.submit(self.run_doing, home, "show", "--json"))
                results = [future.result() for future in futures]
            for result in results:
                self.assertEqual(result.returncode, 0, result.stderr)
            shown = self.run_doing(home, "show", "--json")
            self.assertEqual(shown.returncode, 0, shown.stderr)
            rows = json.loads(shown.stdout)
            self.assertEqual(sorted(row["description"] for row in rows),
                             sorted(descriptions))
            self.assertEqual(len({row["id"] for row in rows}), 16)

    def test_unicode_home_directory_round_trip(self):
        """Use the native home directory even when its path is not ASCII."""
        with tempfile.TemporaryDirectory() as root:
            home = str(Path(root) / "profile-\u03bb")
            Path(home).mkdir()
            created = self.run_doing(home, "task", "Task \u03bb")
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertTrue((Path(home) / ".better-code" / "doing.md").is_file())
            shown = self.run_doing(home, "show", "--json")
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual(json.loads(shown.stdout)[0]["description"], "Task \u03bb")

    def test_redirected_storage_is_rejected(self):
        """Reject a storage symlink or Windows junction without writing through it."""
        with tempfile.TemporaryDirectory() as home:
            target = Path(home) / "target"
            target.mkdir()
            link = Path(home) / ".better-code"
            link_directory(link, target)
            for args in (("task", "Must not write"), ("show",)):
                result = self.run_doing(home, *args)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, "")
            self.assertEqual(list(target.iterdir()), [])

    def test_redirected_ledger_is_rejected(self):
        """Reject a redirected ledger without traversing it or overwriting it."""
        with tempfile.TemporaryDirectory() as home:
            target = Path(home) / "target"
            target.mkdir()
            marker = target / "untouched"
            marker.write_text("original")
            storage = Path(home) / ".better-code"
            storage.mkdir()
            link_directory(storage / "doing.md", target)
            for args in (("show",), ("task", "Must not write")):
                result = self.run_doing(home, *args)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, "")
            self.assertEqual(marker.read_text(), "original")

    def test_missing_ledger_read_does_not_create_storage(self):
        """Show an empty ledger without creating the storage directory."""
        with tempfile.TemporaryDirectory() as home:
            result = self.run_doing(home, "show", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), [])
            self.assertFalse((Path(home) / ".better-code").exists())


class InProcessCLI(unittest.TestCase):
    """CLI fixture for injecting operating-system failures."""

    def run_main(self, home, *args):
        """Invoke the CLI in process so filesystem errors can be injected."""
        stdout, stderr = io.StringIO(), io.StringIO()
        code = 0
        with mock.patch.dict(os.environ, HOME=home, USERPROFILE=home):
            with mock.patch.object(sys, "argv", [str(SCRIPT), *args]):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    try:
                        HELPER["main"]()
                    except SystemExit as error:
                        code = error.code
        return subprocess.CompletedProcess(args, code, stdout.getvalue(),
                                           stderr.getvalue())


@unittest.skipIf(os.name == "nt", "POSIX directory synchronization")
class LedgerSyncTests(InProcessCLI):
    """Check synchronization and failure reporting with real ledger files."""

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


@unittest.skipUnless(os.name == "nt", "Native Windows storage")
class WindowsStoreTests(InProcessCLI):
    """Exercise native replacement, locking and failure reporting."""

    def test_show_does_not_need_write_access_to_lock_file(self):
        """Read a ledger when its persistent writer lock is read-only."""
        with tempfile.TemporaryDirectory() as home:
            created = self.run_main(home, "task", "Readable task")
            self.assertEqual(created.returncode, 0, created.stderr)
            lock = Path(home) / ".better-code" / ".doing.lock"
            lock.chmod(stat.S_IREAD)
            try:
                shown = self.run_main(home, "show", "--json")
                self.assertEqual(shown.returncode, 0, shown.stderr)
                self.assertEqual(json.loads(shown.stdout)[0]["description"],
                                 "Readable task")
            finally:
                lock.chmod(stat.S_IREAD | stat.S_IWRITE)

    def test_show_does_not_provision_lock_but_done_does(self):
        """Read without creating a lock, but still serialize completion writes."""
        with tempfile.TemporaryDirectory() as home:
            created = self.run_main(home, "task", "Existing task")
            self.assertEqual(created.returncode, 0, created.stderr)
            task_id = json.loads(created.stdout)["id"]
            lock = Path(home) / ".better-code" / ".doing.lock"
            lock.unlink()
            shown = self.run_main(home, "show", "--json")
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual(json.loads(shown.stdout)[0]["id"], task_id)
            self.assertFalse(lock.exists())
            completed = self.run_main(home, "done", task_id)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(lock.is_file())
            history = self.run_main(home, "show", "all", "--json")
            self.assertEqual(history.returncode, 0, history.stderr)
            self.assertTrue(json.loads(history.stdout)[0]["completed"])

    def test_replacement_failure_reports_uncertain_task_without_data_loss(self):
        """Report replacement errors and preserve readable existing work."""
        backend = sys.modules["windows_store"]
        for command in ("task", "done"):
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as home:
                    first = self.run_main(home, "task", "Existing task")
                    self.assertEqual(first.returncode, 0, first.stderr)
                    task_id = json.loads(first.stdout)["id"]
                    ledger = Path(home) / ".better-code" / "doing.md"
                    previous = ledger.read_bytes()
                    argument = "New task" if command == "task" else task_id
                    with mock.patch.object(backend, "move_file", return_value=0):
                        with mock.patch.object(backend.ctypes, "get_last_error",
                                               return_value=5):
                            result = self.run_main(home, command, argument)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("may have been saved", result.stderr)
                    self.assertIn("show all --json", result.stderr)
                    self.assertRegex(result.stderr, r"Task [0-9a-f]{32} update")
                    if command == "done":
                        self.assertIn(task_id, result.stderr)
                    self.assertEqual(ledger.read_bytes(), previous)
                    self.assertEqual(sorted(path.name for path in ledger.parent.iterdir()),
                                     [".doing.lock", "doing.md"])
                    retry = self.run_main(home, command, argument)
                    self.assertEqual(retry.returncode, 0, retry.stderr)

    def test_replacement_requests_write_through_after_content_sync(self):
        """Flush contents before requesting a same-directory write-through move."""
        backend = sys.modules["windows_store"]
        with tempfile.TemporaryDirectory() as home:
            events = []
            real_sync, real_move = os.fsync, backend.move_file

            def sync(descriptor):
                """Record the real content flush."""
                self.assertTrue(stat.S_ISREG(os.fstat(descriptor).st_mode))
                self.assertEqual(sys.stdout.getvalue(), "")
                real_sync(descriptor)
                events.append("sync")

            def move(source, destination, flags):
                """Verify the replacement protocol while performing the real move."""
                self.assertEqual(sys.stdout.getvalue(), "")
                self.assertEqual(Path(source).parent, Path(destination).parent)
                self.assertEqual(flags, 0x00000009)
                events.append("replace")
                return real_move(source, destination, flags)

            with mock.patch("os.fsync", side_effect=sync):
                with mock.patch.object(backend, "move_file", side_effect=move):
                    result = self.run_main(home, "task", "Flushed task")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(events, ["sync", "replace"])
            shown = self.run_main(home, "show", "--json")
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual(json.loads(shown.stdout)[0]["description"], "Flushed task")

    def test_redirected_lock_file_is_rejected(self):
        """Reject lock-file redirection without changing the target directory."""
        with tempfile.TemporaryDirectory() as home:
            storage = Path(home) / ".better-code"
            storage.mkdir()
            target = Path(home) / "target"
            target.mkdir()
            link_directory(storage / ".doing.lock", target)
            result = self.run_main(home, "task", "Must not write")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertEqual(list(target.iterdir()), [])
            self.assertFalse((storage / "doing.md").exists())


if __name__ == "__main__":
    unittest.main()
