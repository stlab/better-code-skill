---
title: "Plugin release and CI test selection"
entity_type: procedure
confidence: 0.70
created: 2026-11-18T17:14:37Z
last_accessed: 2026-11-18T17:14:37Z
last_reinforced: 2026-11-18T17:14:37Z
access_count: 1
sources:
  - ".github/workflows/release.yml:1"
  - ".github/workflows/release.yml:50"
  - ".github/scripts/update-plugin-versions.py:28"
  - ".github/workflows/doing-tests.yml:3"
relationships:
  - type: extends
    target: "Architecture Overview"
tags: ["release", "ci", "versioning", "manifests", "workflows"]
tier: procedures
source: inferred
---

# Plugin release and CI test selection

Manifest versions are updated automatically by the release workflow: on a published non-prerelease, non-draft GitHub release, the 'publish' job (release.yml, after the 'test' job passes) runs .github/scripts/update-plugin-versions.py TAG, which strips a leading 'v', requires strict X.Y.Z, finds exactly one 'better-code' entry in marketplace.json, refuses any downgrade relative to either manifest, and rewrites .claude-plugin/plugin.json and marketplace.json only when versions differ. The job commits and pushes the manifests to the default branch with up to 3 attempts, refetching and reapplying on each retry, and exits successfully if nothing changed. Tests are split by path filter: doing-tests.yml (hooks/**, .claude-plugin/**, skills/doing/**, .github/workflows/doing-tests.yml) runs 'python -m unittest discover -s skills/doing/tests' on Ubuntu and Windows with Python 3.9 and 3.14, and on macOS with Python 3.14 only; all five jobs use Node 22.20.0. release.yml's test job runs 'python -m unittest discover -s .github/scripts/tests' for .github/scripts, the release workflow, and .claude-plugin changes. Run the matching unittest command locally for the directory you change. Scoped to revision 8b6a965.
