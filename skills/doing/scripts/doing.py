#!/usr/bin/env python3
"""Maintain a local Markdown ledger of started work."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, replace
import html
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

if os.name == "nt":
    from windows_store import WindowsStore
else:
    try:
        import fcntl
    except ImportError as error:
        raise SystemExit("doing: POSIX file locking is required") from error


HEADER = (
    "| Description | Location | Session | tmux |\n"
    "| --- | --- | --- | --- |\n"
)
ROW = re.compile(
    r"^\| \[([ x])\] (.*?) <!-- doing:([0-9a-f]{32}):([0-9a-f]*) -->"
    r" \| (.*?) \| (.*?) \| (.*?) \|$"
)
UNKNOWN = "unavailable"
# NUL cannot occur in a command-line ID; older helpers preserve this opaque field.
OWNERSHIP_PREFIX = "\0doing:"


class LedgerError(Exception):
    """A ledger operation could not be completed."""


@dataclass(frozen=True)
class Entry:
    """A task and its session metadata."""

    id: str
    description: str
    location: str
    session: str
    session_id: str | None
    tmux: str
    completed: bool = False
    parent_session_id: str | None = None


def escape_cell(value):
    """Encode text without introducing Markdown table delimiters."""
    return (
        html.escape(value)
        .replace("|", "&#124;")
        .replace("\n", "&#10;")
        .replace("\r", "&#13;")
    )


def parse_session_metadata(encoded):
    """Return session and parent IDs, or raise LedgerError for malformed metadata.

    Time and additional space: O(n), where n is the metadata size.
    """
    try:
        value = bytes.fromhex(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise LedgerError("Malformed session ID in ledger") from error
    if not value.startswith(OWNERSHIP_PREFIX):
        return value or None, None
    try:
        owners = json.loads(value[len(OWNERSHIP_PREFIX):])
    except json.JSONDecodeError as error:
        raise LedgerError("Malformed ownership metadata in ledger") from error
    if (
        not isinstance(owners, list) or len(owners) != 2
        or (owners[0] is not None and not isinstance(owners[0], str))
        or not isinstance(owners[1], str) or not owners[1]
    ):
        raise LedgerError("Malformed ownership metadata in ledger")
    return owners[0] or None, owners[1]


def parse_ledger(text):
    """Parse the ledger or raise LedgerError without changing it.

    Time and additional space: O(n), where n is the ledger size.
    """
    if not text.startswith(HEADER):
        raise LedgerError("Malformed ledger header")
    entries = []
    seen = set()
    lines = text[len(HEADER):].split("\n")
    if lines[-1] == "":
        lines.pop()
    for line in lines:
        match = ROW.fullmatch(line)
        if match is None:
            raise LedgerError("Malformed ledger row")
        (checked, description, task_id, session_hex,
         location, session, tmux) = match.groups()
        if task_id in seen:
            raise LedgerError("Duplicate task ID in ledger")
        session_id, parent_session_id = parse_session_metadata(session_hex)
        entries.append(
            Entry(
                task_id,
                html.unescape(description),
                html.unescape(location),
                html.unescape(session),
                session_id,
                html.unescape(tmux),
                checked == "x",
                parent_session_id,
            )
        )
        seen.add(task_id)
    return entries


def render_ledger(entries, for_display=False):
    """Render a storage table, or a display table with visible task IDs.

    Time and additional space: O(n), where n is the rendered size.
    """
    lines = [HEADER if not for_display else (
        "| ID | Description | Location | Session | tmux |\n"
        "| --- | --- | --- | --- | --- |\n"
    )]
    for entry in entries:
        status = "x" if entry.completed else " "
        metadata = ""
        if not for_display:
            ownership = entry.session_id or ""
            if entry.parent_session_id:
                ownership = OWNERSHIP_PREFIX + json.dumps(
                    [entry.session_id, entry.parent_session_id],
                    separators=(",", ":"),
                )
            session_hex = ownership.encode("utf-8").hex()
            metadata = f" <!-- doing:{entry.id}:{session_hex} -->"
        visible_id = f"{entry.id} | " if for_display else ""
        lines.append(
            f"| {visible_id}[{status}] {escape_cell(entry.description)}{metadata} | "
            f"{escape_cell(entry.location)} | {escape_cell(entry.session)} | "
            f"{escape_cell(entry.tmux)} |\n"
        )
    return "".join(lines)


def open_store(create, writable=True):
    """Open the storage directory without following a symlink.

    Returns None if the directory is absent and create is false.
    POSIX creation requests sync the parent directory, including on retries.
    Read-only Windows access does not provision a writer lock.
    """
    home = Path.home()
    if not home.is_absolute():
        raise LedgerError("Home directory must be an absolute path")
    path = home / ".better-code"
    if os.name == "nt":
        return WindowsStore.open(path, create, writable)
    if create:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        if not create:
            return None
        raise
    if stat.S_ISLNK(mode):
        raise LedgerError("Storage directory is a symlink")
    if not stat.S_ISDIR(mode):
        raise LedgerError("Storage path is not a directory")
    if create:
        parent = os.open(home, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


def read_ledger(directory):
    """Read entries from a regular ledger file, or return an empty list.

    Time and additional space: O(n), where n is the ledger size.
    """
    if os.name == "nt":
        text = directory.read()
        return [] if text is None else parse_ledger(text)
    try:
        mode = os.stat("doing.md", dir_fd=directory, follow_symlinks=False).st_mode
    except FileNotFoundError:
        return []
    if stat.S_ISLNK(mode):
        raise LedgerError("Ledger is a symlink")
    if not stat.S_ISREG(mode):
        raise LedgerError("Ledger is not a regular file")
    descriptor = os.open("doing.md", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    with os.fdopen(descriptor, encoding="utf-8") as file:
        return parse_ledger(file.read())


def replace_ledger(directory, entries, task_id):
    """Replace the ledger and request platform-specific metadata persistence.

    A metadata persistence failure reports task_id and an uncertain save status;
    a visible replacement is not rolled back.

    Time and additional space: O(n), where n is the rendered ledger size.
    """
    if os.name == "nt":
        directory.replace(render_ledger(entries), task_id)
        return
    name = f".doing-{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600, dir_fd=directory,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(render_ledger(entries))
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, "doing.md", src_dir_fd=directory, dst_dir_fd=directory)
        try:
            os.fsync(directory)
        except OSError as error:
            raise LedgerError(
                f"Task {task_id} update may have been saved; "
                f"verify with show all --json before retrying: {error}"
            ) from error
    finally:
        try:
            os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass


@contextmanager
def store_lock(directory):
    """Hold a ledger lock, except for Windows snapshot readers."""
    if os.name == "nt":
        directory.lock()
    else:
        fcntl.flock(directory, fcntl.LOCK_EX)
    try:
        yield
    finally:
        if os.name == "nt":
            directory.unlock()
        else:
            fcntl.flock(directory, fcntl.LOCK_UN)


def close_store(directory):
    """Release an opened store's operating-system resources."""
    if os.name == "nt":
        directory.close()
    else:
        os.close(directory)


def write_change(directory, command, args):
    """Apply one task creation or completion under an exclusive lock.

    Time and additional space: O(n), where n is the ledger size.
    """
    with store_lock(directory):
        entries = read_ledger(directory)
        if command == "task":
            task_id = uuid.uuid4().hex
            while any(entry.id == task_id for entry in entries):
                task_id = uuid.uuid4().hex
            entries.append(
                Entry(
                    task_id, args.description, args.location or UNKNOWN,
                    args.session_name or UNKNOWN, args.session_id or None,
                    args.tmux or UNKNOWN,
                    parent_session_id=args.parent_session_id or None,
                )
            )
        else:
            matches = [
                index for index, entry in enumerate(entries)
                if entry.id == args.id and not entry.completed
            ]
            if len(matches) != 1:
                raise LedgerError("Task ID does not identify exactly one open task")
            index = matches[0]
            entries[index] = replace(entries[index], completed=True)
            task_id = args.id
        replace_ledger(directory, entries, task_id)
        return task_id


def entry_json(entry):
    """Return a JSON-serializable description of an entry."""
    return {
        "id": entry.id,
        "description": entry.description,
        "location": entry.location,
        "session": entry.session,
        "session_id": entry.session_id,
        "parent_session_id": entry.parent_session_id,
        "tmux": entry.tmux,
        "completed": entry.completed,
    }


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    task = subcommands.add_parser("task", help="Record a started task")
    task.add_argument("description")
    task.add_argument("--location")
    task.add_argument("--session-name")
    task.add_argument("--session-id")
    task.add_argument("--parent-session-id", help="Session coordinating delegated work")
    task.add_argument("--tmux")
    done = subcommands.add_parser("done", help="Complete one task by ID")
    done.add_argument("id")
    show = subcommands.add_parser("show", help="Show tasks")
    show.add_argument("scope", nargs="?", choices=("open", "all"), default="open")
    show.add_argument("--json", action="store_true")
    show.add_argument("--session-id", help="Include this session and its delegated tasks")
    return parser.parse_args()


def main():
    """Execute the requested ledger operation."""
    args = parse_args()
    try:
        if args.command == "task" and not args.description.strip():
            raise LedgerError("Task description must not be empty")
        directory = open_store(args.command == "task",
                               writable=args.command != "show")
        if directory is None:
            if args.command == "done":
                raise LedgerError("Task ledger does not exist")
            entries = []
        else:
            try:
                if args.command != "show":
                    task_id = write_change(directory, args.command, args)
                    print(json.dumps({"id": task_id}))
                    return
                with store_lock(directory):
                    entries = read_ledger(directory)
            finally:
                close_store(directory)
        if args.scope == "open":
            entries = [entry for entry in entries if not entry.completed]
        if args.session_id is not None:
            if not args.session_id.strip():
                raise LedgerError("Session ID must not be empty")
            entries = [
                entry for entry in entries
                if args.session_id in (entry.session_id, entry.parent_session_id)
            ]
        if args.json:
            print(json.dumps([entry_json(entry) for entry in entries]))
        else:
            print(render_ledger(entries, for_display=True), end="")
    except (LedgerError, OSError, UnicodeError) as error:
        print(f"doing: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
