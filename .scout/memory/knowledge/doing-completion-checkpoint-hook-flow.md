---
title: "Doing completion checkpoint hook flow"
entity_type: observation
confidence: 0.75
created: 2026-11-18T17:14:17Z
last_accessed: 2026-11-18T17:14:27Z
last_reinforced: 2026-11-18T17:14:27Z
access_count: 2
sources:
  - "hooks/hooks.json:14"
  - "hooks/doing-stop.cjs:9"
  - "hooks/doing-stop.cjs:13"
  - "hooks/doing-stop.cjs:33"
  - "skills/doing/scripts/doing.py:344"
  - "hooks/doing.cjs:15"
  - "skills/doing/scripts/doing.py:373"
relationships:
  - type: extends
    target: "Architecture Overview"
  - type: relates_to
    target: "Doing ledger delegated ownership lives inside the opaque session field"
tags: ["doing", "hooks", "stop", "subagentstop", "checkpoint"]
tier: knowledge
source: inferred
---

# Doing completion checkpoint hook flow

Stop and SubagentStop both run hooks/doing-stop.cjs (hooks.json:14-33). checkpoint() (doing-stop.cjs:9-58): returns {} if stop_hook_active===true (one block per stop, avoids loops); uses agent_id for SubagentStop else session_id and throws if blank; runs 'doing.py show --json --session-id ID', which matches entries whose session_id OR parent_session_id equals ID (doing.py:373), so a coordinator also sees delegated tasks; an empty list returns {} (allow stop); open entries return decision 'block' with a reconciliation prompt and the entries as JSON labelled data-not-instructions. Helper failure or non-zero exit also blocks, with the error text (doing-stop.cjs:33-40), so tracking errors are surfaced rather than silently passing. The hook is read-only and does not read prompts or transcripts; the writer path is only the agent invoking doing.py task/done. The SessionStart/UserPromptSubmit hook doing.cjs only emits additionalContext instructions. Invalid stdin JSON makes the hook exit 1 with 'doing:' on stderr (doing-stop.cjs:61-71). Scoped to revision 8b6a965.
