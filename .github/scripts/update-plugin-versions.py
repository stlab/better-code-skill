"""Synchronize both manifests from a stable release tag, such as `v1.1.0`."""

import argparse
import json
from pathlib import Path
import re


def _parse_version(version: str) -> tuple[int, ...]:
    """Return numeric components of an X.Y.Z version, or raise ValueError.

    Time and space are linear in the version's length.
    """
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError(f"Invalid stable version: {version!r}; expected X.Y.Z")
    return tuple(map(int, version.split(".")))


def main() -> None:
    """Update both manifest versions from the command-line release tag.

    Reject invalid versions and downgrades before writing either manifest.
    Leave files unchanged when their versions already match. Time and space
    are linear in the combined manifest and tag sizes.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="Stable release tag, with an optional leading v")
    args = parser.parse_args()
    try:
        version = args.tag.removeprefix("v")
        release_version = _parse_version(version)
        plugin_path = Path(".claude-plugin/plugin.json")
        marketplace_path = Path(".claude-plugin/marketplace.json")
        plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        entries = [entry for entry in marketplace["plugins"]
                   if entry["name"] == "better-code"]
        if len(entries) != 1:
            raise ValueError("Marketplace must contain exactly one better-code entry")
        manifests = (
            (plugin_path, plugin, plugin),
            (marketplace_path, marketplace, entries[0]),
        )
        for path, _, entry in manifests:
            if _parse_version(entry["version"]) > release_version:
                raise ValueError(
                    f"Refusing to downgrade {path} from {entry['version']} to {version}"
                )
        for path, document, entry in manifests:
            if entry["version"] != version:
                entry["version"] = version
                path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
