#!/usr/bin/env python3
"""Maintain a local Markdown ledger of started work."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import html
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

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


def escape_cell(value):
    """Encode text without introducing Markdown table delimiters."""
    return (
        html.escape(value)
        .replace("|", "&#124;")
        .replace("\n", "&#10;")
        .replace("\r", "&#13;")
    )


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
        checked, description, task_id, session_hex, location, session, tmux = (
            match.groups()
        )
        if task_id in seen:
            raise LedgerError("Duplicate task ID in ledger")
        try:
            session_id = bytes.fromhex(session_hex).decode("utf-8") or None
        except (ValueError, UnicodeDecodeError) as error:
            raise LedgerError("Malformed session ID in ledger") from error
        entries.append(
            Entry(
                task_id,
                html.unescape(description),
                html.unescape(location),
                html.unescape(session),
                session_id,
                html.unescape(tmux),
                checked == "x",
            )
        )
        seen.add(task_id)
    return entries


def render_ledger(entries, include_ids=True):
    """Render entries as a Markdown table.

    Time and additional space: O(n), where n is the rendered size.
    """
    lines = [HEADER]
    for entry in entries:
        status = "x" if entry.completed else " "
        metadata = ""
        if include_ids:
            session_id = (entry.session_id or "").encode("utf-8").hex()
            metadata = f" <!-- doing:{entry.id}:{session_id} -->"
        lines.append(
            f"| [{status}] {escape_cell(entry.description)}{metadata} | "
            f"{escape_cell(entry.location)} | {escape_cell(entry.session)} | "
            f"{escape_cell(entry.tmux)} |\n"
        )
    return "".join(lines)


def open_store(create):
    """Open the storage directory without following a symlink.

    Returns None if the directory is absent and create is false.
    Creation requests sync the parent directory, including on retries.
    """
    home = Path.home()
    if not home.is_absolute():
        raise LedgerError("Home directory must be an absolute path")
    path = home / ".better-code"
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
    """Atomically replace the ledger and sync its directory.

    A directory sync failure reports task_id and an uncertain save status;
    the replacement is already visible and is not rolled back.

    Time and additional space: O(n), where n is the rendered ledger size.
    """
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


def write_change(directory, command, args):
    """Apply one task creation or completion under an exclusive lock.

    Time and additional space: O(n), where n is the ledger size.
    """
    fcntl.flock(directory, fcntl.LOCK_EX)
    try:
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
    finally:
        fcntl.flock(directory, fcntl.LOCK_UN)


def entry_json(entry):
    """Return a JSON-serializable description of an entry."""
    return {
        "id": entry.id,
        "description": entry.description,
        "location": entry.location,
        "session": entry.session,
        "session_id": entry.session_id,
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
    task.add_argument("--tmux")
    done = subcommands.add_parser("done", help="Complete one task by ID")
    done.add_argument("id")
    show = subcommands.add_parser("show", help="Show tasks")
    show.add_argument("scope", nargs="?", choices=("open", "all"), default="open")
    show.add_argument("--json", action="store_true")
    return parser.parse_args()


def main():
    """Execute the requested ledger operation."""
    args = parse_args()
    try:
        if args.command == "task" and not args.description.strip():
            raise LedgerError("Task description must not be empty")
        directory = open_store(args.command == "task")
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
                entries = read_ledger(directory)
            finally:
                os.close(directory)
        if args.scope == "open":
            entries = [entry for entry in entries if not entry.completed]
        if args.json:
            print(json.dumps([entry_json(entry) for entry in entries]))
        else:
            print(render_ledger(entries, include_ids=False), end="")
    except (LedgerError, OSError, UnicodeError) as error:
        print(f"doing: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
