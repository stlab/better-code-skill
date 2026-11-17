"""Exercise release version updates against temporary plugin manifests."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "update-plugin-versions.py"


class ReleaseVersionTests(unittest.TestCase):
    """Verify version publication and validation without repository writes."""

    def setUp(self):
        """Create isolated manifests with an unrelated marketplace entry."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        manifests = self.root / ".claude-plugin"
        manifests.mkdir()
        self.plugin = manifests / "plugin.json"
        self.marketplace = manifests / "marketplace.json"
        self.plugin.write_text(
            '{\n  "name": "better-code",\n  "version": "1.0.0"\n}\n',
            encoding="utf-8",
        )
        self.marketplace.write_text(
            json.dumps(
                {
                    "name": "better-code-marketplace",
                    "plugins": [
                        {"name": "other", "version": "9.0.0", "source": "./other"},
                        {"name": "better-code", "version": "1.0.0", "source": "./"},
                    ],
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    def run_update(self, tag):
        """Run the updater in the temporary repository."""
        return subprocess.run(
            [sys.executable, str(SCRIPT), tag],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_updates_both_manifests_and_preserves_other_metadata(self):
        """Publish the release version without changing unrelated metadata."""
        for tag, version in (("v1.1.0", "1.1.0"), ("1.10.0", "1.10.0")):
            with self.subTest(tag=tag):
                result = self.run_update(tag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    json.loads(self.plugin.read_text(encoding="utf-8")),
                    {"name": "better-code", "version": version},
                )
                self.assertEqual(
                    json.loads(self.marketplace.read_text(encoding="utf-8")),
                    {
                        "name": "better-code-marketplace",
                        "plugins": [
                            {"name": "other", "version": "9.0.0", "source": "./other"},
                            {"name": "better-code", "version": version, "source": "./"},
                        ],
                    },
                )

    def test_rerun_does_not_rewrite_manifests(self):
        """Leave already-published manifests byte-for-byte unchanged."""
        result = self.run_update("v1.1.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        before = [(path.read_bytes(), path.stat().st_mtime_ns)
                  for path in (self.plugin, self.marketplace)]
        result = self.run_update("v1.1.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [(path.read_bytes(), path.stat().st_mtime_ns)
             for path in (self.plugin, self.marketplace)],
            before,
        )

    def test_invalid_tags_fail_without_writes(self):
        """Reject non-stable or malformed versions before updating files."""
        before = [path.read_bytes() for path in (self.plugin, self.marketplace)]
        for tag in ("v1.2", "v01.2.3", "v1.2.3-rc.1", "v1.2.3+build", "bad", ""):
            with self.subTest(tag=tag):
                result = self.run_update(tag)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid stable version", result.stderr)
                self.assertEqual(
                    [path.read_bytes() for path in (self.plugin, self.marketplace)],
                    before,
                )

    def test_downgrade_of_either_manifest_fails_without_writes(self):
        """Reject stale releases without partially updating the other file."""
        for path in (self.plugin, self.marketplace):
            with self.subTest(path=path.name):
                original = path.read_text(encoding="utf-8")
                path.write_text(original.replace("1.0.0", "1.10.0"), encoding="utf-8")
                before = [item.read_bytes() for item in (self.plugin, self.marketplace)]
                result = self.run_update("v1.2.0")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("downgrade", result.stderr)
                self.assertEqual(
                    [item.read_bytes() for item in (self.plugin, self.marketplace)],
                    before,
                )
                path.write_text(original, encoding="utf-8")

    def test_missing_marketplace_entry_fails_without_writes(self):
        """Report a missing plugin rather than updating only one manifest."""
        self.marketplace.write_text('{"plugins": []}\n', encoding="utf-8")
        before = [path.read_bytes() for path in (self.plugin, self.marketplace)]
        result = self.run_update("v1.1.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one better-code entry", result.stderr)
        self.assertEqual(
            [path.read_bytes() for path in (self.plugin, self.marketplace)],
            before,
        )


if __name__ == "__main__":
    unittest.main()
