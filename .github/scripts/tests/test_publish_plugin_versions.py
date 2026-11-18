"""Exercise the publishing shell against concurrent local Git writers."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[3]
UPDATER = ROOT / ".github/scripts/update-plugin-versions.py"
WORKFLOW = ROOT / ".github/workflows/release.yml"


class PublicationTests(unittest.TestCase):
    """Verify publication retries without changing any shared repository."""

    def setUp(self):
        """Create a bare remote and independent publisher and writer clones."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.remote = self.root / "remote.git"
        self.publisher = self.root / "publisher"
        self.writer = self.root / "writer"
        self.attempts = self.root / "attempts"
        self.git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.git(self.root, "init", "--initial-branch=main", str(self.publisher))
        self.configure(self.publisher)
        manifests = self.publisher / ".claude-plugin"
        manifests.mkdir()
        (manifests / "plugin.json").write_text(
            '{"name":"better-code","version":"1.0.0"}\n', encoding="utf-8"
        )
        (manifests / "marketplace.json").write_text(
            '{"plugins":[{"name":"better-code","version":"1.0.0"}]}\n',
            encoding="utf-8",
        )
        script = self.publisher / ".github/scripts/update-plugin-versions.py"
        script.parent.mkdir(parents=True)
        shutil.copyfile(UPDATER, script)
        self.git(self.publisher, "add", ".")
        self.git(self.publisher, "commit", "-m", "Initial manifests")
        self.git(self.publisher, "tag", "v1.1.0")
        self.git(self.publisher, "remote", "add", "origin", str(self.remote))
        self.git(self.publisher, "push", "origin", "main", "--tags")
        self.git(self.root, "clone", str(self.remote), str(self.writer))
        self.configure(self.writer)

    def git(self, cwd, *args):
        """Run Git successfully and return its captured output."""
        return subprocess.check_output(
            ["git", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT
        ).strip()

    def configure(self, repo):
        """Configure an unsigned fixture author and repository-local hooks."""
        self.git(repo, "config", "user.name", "Release test")
        self.git(repo, "config", "user.email", "release-test@example.invalid")
        self.git(repo, "config", "commit.gpgsign", "false")
        self.git(repo, "config", "core.hooksPath", ".git/hooks")

    def install_race(self, *, every_push=False, newer_release=False):
        """Advance the remote in a real pre-push hook, once or on every push."""
        hook = self.publisher / ".git/hooks/pre-push"
        hook.write_text(
            "#!/bin/bash\nset -euo pipefail\n"
            'if [ "$EVERY_PUSH" = 1 ] || [ ! -f "$ATTEMPTS" ]; then\n'
            '  echo race >> "$ATTEMPTS"\n'
            '  cp "$ATTEMPTS" "$WRITER/concurrent.txt"\n'
            '  if [ "$NEWER_RELEASE" = 1 ]; then\n'
            '    (cd "$WRITER" && "$PYTHON" '
            '.github/scripts/update-plugin-versions.py v2.0.0)\n'
            "  fi\n"
            '  git -C "$WRITER" add .\n'
            '  git -C "$WRITER" commit -m "Concurrent branch update"\n'
            '  git -C "$WRITER" push origin main\n'
            "fi\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)
        self.race_env = {
            "WRITER": str(self.writer),
            "ATTEMPTS": str(self.attempts),
            "PYTHON": sys.executable,
            "EVERY_PUSH": str(int(every_push)),
            "NEWER_RELEASE": str(int(newer_release)),
        }

    def publish(self):
        """Run the workflow's updater and actual final publishing shell block."""
        subprocess.run(
            [sys.executable, ".github/scripts/update-plugin-versions.py", "v1.1.0"],
            cwd=self.publisher, check=True, capture_output=True, text=True,
        )
        step = WORKFLOW.read_text(encoding="utf-8").split(
            "      - name: Commit and push manifest versions\n", 1
        )[1]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1])
        return subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", script],
            cwd=self.publisher, capture_output=True, text=True, check=False,
            env=dict(os.environ, RELEASE_TAG="v1.1.0", DEFAULT_BRANCH="main",
                     **self.race_env),
        )

    def remote_version(self):
        """Return the version currently published on the remote default branch."""
        return json.loads(self.git(
            self.root, "--git-dir", str(self.remote), "show",
            "main:.claude-plugin/plugin.json",
        ))["version"]

    def test_retries_after_merge_and_preserves_concurrent_commit(self):
        """Recover from a rejected push without losing a concurrent merge."""
        self.install_race()
        tag = self.git(self.publisher, "rev-parse", "v1.1.0")
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_version(), "1.1.0")
        self.assertEqual(
            self.git(self.root, "--git-dir", str(self.remote), "show",
                     "main:concurrent.txt"),
            "race",
        )
        self.assertEqual(self.git(self.publisher, "rev-parse", "HEAD^"),
                         self.git(self.writer, "rev-parse", "HEAD"))
        self.assertEqual(self.git(self.publisher, "rev-parse", "v1.1.0"), tag)
        published = self.git(self.publisher, "rev-parse", "HEAD")
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git(self.publisher, "rev-parse", "HEAD"), published)

    def test_retry_rejects_a_concurrently_published_newer_version(self):
        """Keep a newer release instead of replaying the stale manifest commit."""
        self.install_race(newer_release=True)
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("downgrade", result.stderr)
        self.assertEqual(self.remote_version(), "2.0.0")

    def test_retry_exhaustion_fails_explicitly_after_three_attempts(self):
        """Bound repeated concurrent push failures and leave the remote intact."""
        self.install_race(every_push=True)
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("after 3 attempts", result.stdout + result.stderr)
        self.assertEqual(self.attempts.read_text(encoding="utf-8").splitlines(),
                         ["race", "race", "race"])
        self.assertEqual(self.remote_version(), "1.0.0")


if __name__ == "__main__":
    unittest.main()
