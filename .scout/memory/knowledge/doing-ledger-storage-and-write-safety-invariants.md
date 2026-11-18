---
title: "Doing ledger storage and write safety invariants"
entity_type: observation
confidence: 0.75
created: 2026-11-18T17:14:37Z
last_accessed: 2026-11-18T17:14:37Z
last_reinforced: 2026-11-18T17:14:37Z
access_count: 1
sources:
  - "skills/doing/scripts/doing.py:159"
  - "skills/doing/scripts/doing.py:196"
  - "skills/doing/scripts/doing.py:217"
  - "skills/doing/scripts/doing.py:277"
  - "README.md:91"
relationships:
  - type: extends
    target: "Architecture Overview"
tags: ["doing", "ledger", "locking", "atomic-write", "windows", "posix"]
tier: knowledge
source: inferred
---

# Doing ledger storage and write safety invariants

The ledger is `~/.better-code/doing.md`. Mutations go through `write_change`
(doing.py:277-307) under an exclusive lock and regenerate the whole file.
Parse errors raise `LedgerError` before replacement. Task IDs are 32-hex UUIDs,
de-duplicated against existing IDs; `done` must match exactly one open ID.

On POSIX, `open_store` (doing.py:159-193) refuses a symlinked or non-directory
storage path, creates a missing directory with mode 0700, and opens it with
`O_NOFOLLOW`. `read_ledger` rejects a symlink or non-regular ledger. Writers
use `flock`; `replace_ledger` (doing.py:217-251) writes a 0600 temp file,
fsyncs it, calls `os.replace`, then fsyncs the directory. A directory-fsync
failure after replacement raises a `LedgerError` saying the update "may have
been saved"; check `show all --json` for the task ID before retrying because
replacement is not rolled back (README.md:106-108).

On Windows, opening, reading, replacement, and locking delegate to
`WindowsStore` in `skills/doing/scripts/windows_store.py`, not the POSIX
directory-descriptor and directory-fsync paths (doing.py:170-171,201-203,225-227).
Windows files inherit parent-directory access controls (README.md:94).
`show` takes the lock on POSIX, but Windows `show` reads a snapshot without
creating the lock file (README.md:95). Scoped to revision 8b6a965.
