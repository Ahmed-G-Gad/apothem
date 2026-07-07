# SPDX-License-Identifier: MIT

"""Extract a single version's release notes from CHANGELOG.md.

Purpose: the release.yml workflow needs a clean Markdown body for the GitHub
Release page sourced from the matching ``## [VERSION]`` section of
``CHANGELOG.md``. This module isolates that extraction so it can be unit-tested
independently of the workflow runner.

Contract:
    Given a CHANGELOG.md with ``## [VERSION]`` release sections and a version
    string, write the section body (everything between ``## [VERSION]`` and
    the next ``## [`` heading, exclusive of the heading line itself) to the
    output path.

CLI:
    python scripts/release/extract_release_notes.py \\
        --version 1.2.3 \\
        --changelog CHANGELOG.md \\
        --output release-notes.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SECTION_HEADER_PREFIX = "## ["


def extract_section(changelog: str, version: str) -> str:
    """Return the body of the ``## [VERSION]`` section.

    Args:
        changelog: Full CHANGELOG.md contents.
        version: Semantic version string without the leading ``v``.

    Returns:
        The Markdown body of the matched section, with leading and trailing
        whitespace trimmed. The header line itself is excluded.

    Raises:
        ValueError: If no section matches the requested version.
    """
    target_header = f"{SECTION_HEADER_PREFIX}{version}]"
    lines = changelog.splitlines()

    body: list[str] = []
    inside = False
    for line in lines:
        if line.startswith(target_header):
            inside = True
            continue
        if inside and line.startswith(SECTION_HEADER_PREFIX):
            break
        if inside:
            body.append(line)

    if not inside:
        raise ValueError(
            f"CHANGELOG.md has no '## [{version}]' section. "
            f"Promote the [Unreleased] block to [{version}] before tagging."
        )

    return "\n".join(body).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Semver, e.g. 1.2.3")
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Path to CHANGELOG.md (default: CHANGELOG.md)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the extracted release notes",
    )
    args = parser.parse_args(argv)

    try:
        text = args.changelog.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: changelog not found at {args.changelog}", file=sys.stderr)
        return 2

    try:
        body = extract_section(text, args.version)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    args.output.write_text(body, encoding="utf-8")
    print(f"wrote {len(body)} bytes to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
