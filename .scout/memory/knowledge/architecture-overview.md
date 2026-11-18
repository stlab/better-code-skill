---
title: "Architecture Overview"
entity_type: concept
confidence: 0.70
created: 2026-11-18T17:13:59Z
last_accessed: 2026-11-18T17:13:59Z
last_reinforced: 2026-11-18T17:13:59Z
access_count: 1
sources:
  - ".claude-plugin/plugin.json:1"
  - ".claude-plugin/marketplace.json:5"
  - "hooks/hooks.json:2"
  - "skills/doing/scripts/doing.py:1"
  - "README.md:40"
tags: ["architecture", "plugin", "skills", "better-code", "doing"]
tier: knowledge
source: inferred
---

# Architecture Overview

better-code-skills (inspected at 8b6a965, after PR #6 merge 0fb5300) is a Copilot CLI plugin, not an application. Five skills live as SKILL.md prompt files under skills/ (better-code, contracts, writing, algorithm-research, doing); the only executable code is the Doing task ledger: skills/doing/scripts/doing.py (+ windows_store.py), Node hooks in hooks/ that inject instructions or run a read-only completion checkpoint, and release tooling in .github/scripts. Manifests .claude-plugin/plugin.json and marketplace.json must carry the same version; the release workflow updates both together. Companion skills (Superpowers, Technical Documentation) are separate installs, not bundled. Read first: README.md (user contract), skills/doing/scripts/doing.py (ledger format), hooks/doing-stop.cjs (checkpoint), .github/workflows/*.yml (test/release paths). Aliases / also known as: better-code plugin, Doing helper, plugin layout
