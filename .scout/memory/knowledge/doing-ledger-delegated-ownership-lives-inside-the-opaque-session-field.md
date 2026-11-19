---
title: "Doing ledger delegated ownership lives inside the opaque session field"
entity_type: decision
confidence: 0.75
created: 2026-11-18T17:14:07Z
last_accessed: 2026-11-18T17:21:18Z
last_reinforced: 2026-11-18T17:21:18Z
access_count: 5
sources:
  - "skills/doing/scripts/doing.py:31"
  - "skills/doing/scripts/doing.py:36"
  - "skills/doing/scripts/doing.py:68"
  - "skills/doing/scripts/doing.py:129"
  - "README.md:110"
  - "skills/doing/scripts/doing.py:93"
  - "skills/doing/scripts/doing.py:105"
  - "skills/doing/scripts/doing.py:141"
relationships:
  - type: extends
    target: "Architecture Overview"
tags: ["doing", "ledger", "compatibility", "format", "parent-session-id"]
tier: knowledge
source: inferred
---

# Doing ledger delegated ownership lives inside the opaque session field

## Failure mechanism

Released storage rows contain exactly `<!-- doing:ID:SESSION_HEX -->`. Appending a separate `:PARENT_HEX` field breaks the released ROW regex (doing.py:31-34). parse_ledger uses ROW.fullmatch for every row and raises LedgerError("Malformed ledger row") on the first mismatch (doing.py:93-107), so one delegated row can make the entire shared ledger unreadable to older helpers, blocking show, task, and done rather than just hiding that row. A version marker recognized only by new code cannot repair an already released reader.

## Storage invariant

Keep delegated ownership inside the existing opaque session field. render_ledger (doing.py:129-149) hex-encodes either the ordinary session ID or OWNERSHIP_PREFIX (`\0doing:`) plus compact JSON `[session_id, parent_session_id]`. The NUL prefix cannot collide with a command-line ID. parse_session_metadata (doing.py:68-90) decodes both representations and rejects malformed ownership metadata before a rewrite. Older helpers can preserve the opaque value while reading and rewriting the same grammar; only updated helpers recover parent/child linkage (README.md:110-112).

## Editing consequence

Preserve the released row grammar and opaque-field round trip when extending ownership. Do not add a metadata field or column without an interoperability strategy that works with already installed helpers; new-reader backward compatibility alone is insufficient. Keep the NUL-prefixed representation impossible for command-line IDs. Source anchors refer to inspected revision 8b6a965.
