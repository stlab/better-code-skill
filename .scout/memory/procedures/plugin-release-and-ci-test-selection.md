---
title: "Plugin release and CI test selection"
entity_type: procedure
confidence: 0.75
created: 2026-11-18T17:14:37Z
last_accessed: 2026-11-19T20:15:24Z
last_reinforced: 2026-11-19T20:15:24Z
access_count: 3
sources:
  - ".github/workflows/release.yml:1"
  - ".github/workflows/release.yml:50"
  - ".github/scripts/update-plugin-versions.py:28"
  - ".github/workflows/doing-tests.yml:3"
  - ".github/workflows/release.yml:4"
  - ".github/workflows/release.yml:35"
  - ".github/workflows/release.yml:46"
  - ".github/workflows/release.yml:61"
  - ".github/scripts/update-plugin-versions.py:30"
  - ".github/scripts/update-plugin-versions.py:44"
  - ".github/scripts/tests/test_publish_plugin_versions.py:67"
  - ".github/scripts/tests/test_publish_plugin_versions.py:94"
  - ".github/scripts/tests/test_publish_plugin_versions.py:118"
  - ".github/scripts/tests/test_publish_plugin_versions.py:138"
  - ".github/scripts/tests/test_publish_plugin_versions.py:146"
relationships:
  - type: extends
    target: "Architecture Overview"
tags: ["release", "ci", "versioning", "manifests", "workflows", "concurrency", "pre-push"]
tier: procedures
source: inferred
---

# Plugin release and CI test selection

## Publish versions through the release event

Plugin version discovery depends on the version fields in `.claude-plugin/plugin.json` and the `better-code` entry in `.claude-plugin/marketplace.json`, not on a Git tag alone. The release workflow listens for `release: published`; its `publish` job runs only for a non-prerelease, non-draft release after the test job passes (`.github/workflows/release.yml:4-5,35-36`). Creating a tag or draft does not synchronize the manifests.

The job checks out the repository's default branch, runs `.github/scripts/update-plugin-versions.py TAG`, and commits the two manifests there (`.github/workflows/release.yml:44-53,67-73`). The updater strips a leading `v`, requires strict `X.Y.Z`, requires exactly one `better-code` marketplace entry, rejects a downgrade relative to either manifest before writing, and changes only mismatched versions (`.github/scripts/update-plugin-versions.py:9-16,30-52`). Matching versions make publication a successful no-op. The release tag is not moved: the tagged source can retain older manifest metadata even after the default branch is updated, as checked by `PublicationTests.test_retries_after_merge_and_preserves_concurrent_commit` (`.github/scripts/tests/test_publish_plugin_versions.py:118-136`).

## Rebuild rejected pushes instead of replaying them

The publishing concurrency group serializes publishing jobs, not ordinary merges to the default branch. A merge after checkout can therefore reject the manifest push. Keep publication bounded to three normal push attempts; after rejection, fetch the latest default branch, check out that fetched commit, and rerun the updater before creating a replacement manifest commit (`.github/workflows/release.yml:40-42,61-79`). Do not force-push or blindly replay the old commit: rebuilding preserves concurrent work and reapplies the updater's downgrade protection if a newer version has appeared. Exhausted retries fail explicitly rather than reporting publication success.

## Reproduce races with real Git operations

`PublicationTests.install_race` uses disposable local repositories and a real `pre-push` hook to advance the remote deterministically, without timing sleeps (`.github/scripts/tests/test_publish_plugin_versions.py:21-51,67-91`). The tests cover recovery preserving the concurrent commit and release tag, idempotent reruns, rejection of a concurrently published newer version, and failure after three rejected attempts (`.github/scripts/tests/test_publish_plugin_versions.py:118-154`). Preserve these cases when changing publication.

`PublicationTests.publish` executes the actual workflow shell, extracting it from the step named `Commit and push manifest versions` (`.github/scripts/tests/test_publish_plugin_versions.py:94-108`). Renaming that step or moving its final shell block requires updating the extractor too.

## Select the relevant CI suite

Run `python -m unittest discover -s .github/scripts/tests -v` for release scripts or workflow changes. The release workflow runs that suite on Ubuntu with Python 3.14 for changes under `.github/scripts/**`, `.github/workflows/release.yml`, or `.claude-plugin/**` (`.github/workflows/release.yml:6-32`).

Run `python -m unittest discover -s skills/doing/tests -v` for Doing changes. The Doing workflow selects `hooks/**`, `.claude-plugin/**`, `skills/doing/**`, and its own workflow file. Its five jobs cover Ubuntu and Windows with Python 3.9 and 3.14, and macOS with Python 3.14; all use Node 22.20.0 (`.github/workflows/doing-tests.yml:3-43`).

Verified against revision `70c3e13`; this enriches the existing procedure previously scoped to `8b6a965`.
