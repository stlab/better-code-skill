# Better Code repository instructions

This repository distributes the `better-code` Copilot CLI plugin. Its primary
product is the agent behavior specified in `skills/*/SKILL.md`; executable code
supports Doing task tracking and plugin releases.

## Architecture

Better Code composes separately installed companions: Superpowers governs the
development process, Better Code governs code semantics, and Contracts governs
declaration documentation. Writing invokes Technical Documentation for other
developer documentation. Algorithm Research runs after implementation planning
and before coding. Preserve these boundaries when editing skill prompts.
`README.md` describes installation and the dependency relationships.

`hooks/hooks.json` registers two paths into Doing. `SessionStart` and
`UserPromptSubmit` run `hooks/doing.cjs`, which emits tracking instructions.
`Stop` and `SubagentStop` run `hooks/doing-stop.cjs`, which calls the Python helper
to read session-scoped open tasks and request reconciliation. Hooks never mark
tasks done or write the ledger themselves.

`skills/doing/scripts/doing.py` owns the CLI and the Markdown ledger at
`~/.better-code/doing.md`. POSIX storage uses file locking and directory
synchronization; native Windows storage is isolated in `windows_store.py`.
The helper's `show --json --session-id ID` includes tasks owned by that session
and delegates linked through `--parent-session-id`.

The `.claude-plugin` manifests define the marketplace and the installable plugin;
the plugin namespace is `better-code`, not the repository name.
`.github/workflows/release.yml` connects stable GitHub Release publication to
version synchronization in both manifests on the default branch.

## Test commands

Use Python 3.9 or later and Node.js 22.20 or later. Run these suites from the
repository root:

```bash
python3 -m unittest discover -s skills/doing/tests -v
python3 -m unittest discover -s .github/scripts/tests -v
```

Run one ledger test with unittest's name filter:

```bash
python3 -m unittest discover -s skills/doing/tests \
  -p test_doing.py -k test_displayed_ids_can_complete_the_selected_task -v
```

On native Windows, use `py -3` in place of `python3`.

The Doing CI workflow tests Ubuntu and Windows with Python 3.9 and 3.14, and
macOS with Python 3.14; its Node version is 22.20.0. It selects changes to
`hooks/**`, `.claude-plugin/**`, `skills/doing/**`, and its own workflow.
The release workflow runs `.github/scripts/tests` on Ubuntu with Python 3.14
for changes to release scripts, its own workflow, or the manifests.
Windows-specific storage tests are skipped on POSIX hosts.

## Key conventions

- Skill descriptions, required companion invocations, frontmatter, and headings
  affect agent behavior. Use Superpowers' `writing-skills` workflow when changing
  a skill. Keep declaration-contract guidance in Contracts rather than applying
  Technical Documentation's declaration templates.
- Every type and function, including private declarations, has an adjacent
  contract. Document non-constant time and space complexity; omitted complexity
  uses the project's O(1) documentation convention. Preserve semantic guarantees
  when shortening prose. Put maintainer-only invariants in nearby `[knowledge]`
  comments rather than expanding user-facing explanations.
- Use the Doing helper for ledger changes. Preserve the four-column persisted
  table and its hidden task/session metadata: delegated ownership is encoded
  inside the existing opaque session field for compatibility with older helpers.
  Tests isolate both `HOME` and `USERPROFILE`; keep fixture writes away from the
  developer's real ledger.
- Preserve Doing's storage failure semantics. A failure after replacement can
  leave a visible update; inspect `show all --json` for the reported task ID
  before retrying. Keep the persistent Windows `.doing.lock` file and the
  platform-specific locking/replacement implementations intact.
- The completion hook runs Python from the helper's directory, not the repository
  root. On Windows, it falls back from `py -3` to `python` only when the launcher
  is missing. Keep `stop_hook_active` as the one-block guard and surface helper
  failures instead of treating them as an empty task list.
- Release publication, not tag or draft creation, updates manifest versions.
  The updater accepts stable `X.Y.Z` tags with an optional leading `v`, validates
  both manifests before writing, and rejects downgrades. Publishing leaves the
  release tag unchanged. After a rejected push, rebuild from the latest default
  branch and rerun validation; retain bounded retries and normal, non-force pushes.
- Publication regression tests use disposable local Git remotes and `pre-push`
  hooks to inject concurrent commits. The test helper in
  `.github/scripts/tests/test_publish_plugin_versions.py` extracts the actual
  shell block from the workflow step named
  `Commit and push manifest versions`; update that extractor if the step name or
  final block layout changes.
