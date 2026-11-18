---
title: "Completion hook runs Python from the helper directory with Windows launcher fallback"
entity_type: decision
confidence: 0.75
created: 2026-11-18T17:14:17Z
last_accessed: 2026-11-18T17:14:27Z
last_reinforced: 2026-11-18T17:14:27Z
access_count: 2
sources:
  - "hooks/doing-stop.cjs:19"
  - "hooks/doing-stop.cjs:22"
  - "hooks/doing-stop.cjs:30"
  - "skills/doing/tests/test_hooks.py:145"
  - ".github/workflows/doing-tests.yml:26"
  - ".github/workflows/doing-tests.yml:30"
relationships:
  - type: extends
    target: "Doing completion checkpoint hook flow"
tags: ["doing", "hooks", "windows", "python", "py-launcher", "security"]
tier: knowledge
source: inferred
---

# Completion hook runs Python from the helper directory with Windows launcher fallback

doing-stop.cjs spawns the helper with cwd = path.dirname(helper) (the trusted skills/doing/scripts directory), not the project directory (lines 19-24). On Windows it tries 'py -3 helper...' first and only on ENOENT falls back to 'python helper...' (lines 25-32); elsewhere 'python3'. Rationale: Windows resolves bare executable names from the current directory first, so a repository-root py.exe/python.exe could shadow the launcher; running from the helper directory keeps project-controlled interpreters out. Covered by test_windows_checkpoint_ignores_project_interpreters (test_hooks.py:145-164), which plants a fake py.exe next to the data and expects the real helper's result. Editing consequence: do not switch cwd to the project directory or add search shortcuts without rerunning that test on Windows; CI runs the doing tests on Windows with Python 3.9 and 3.14 (doing-tests.yml:30-31). Scoped to revision 8b6a965; the shadowing mechanism is Windows behavior implied by the code and test, not re-verified on Windows here.
