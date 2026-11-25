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
# GitHub refuses a release body over 125,000 characters; keep a margin.
MAX_BODY_CHARS = 120_000
CHANGELOG_URL = "https://github.com/ahmed-g-gad/apothem/blob/v{version}/CHANGELOG.md"


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


def _split_sections(
    body: str,
) -> tuple[list[str], list[tuple[list[str], list[list[str]]]]]:
    """Split a release body into its lead lines and ``###`` sections.

    Each section is ``(head, entries)``: ``head`` holds the ``###`` line and any
    lines before the first top-level ``- `` entry, and each entry holds one
    top-level bullet with its continuation lines.
    """
    lead: list[str] = []
    sections: list[tuple[list[str], list[list[str]]]] = []
    for line in body.splitlines():
        if line.startswith("### "):
            sections.append(([line], []))
        elif not sections:
            lead.append(line)
        elif line.startswith("- "):
            sections[-1][1].append([line])
        elif sections[-1][1]:
            sections[-1][1][-1].append(line)
        else:
            sections[-1][0].append(line)
    return lead, sections


def fit_to_limit(body: str, version: str, limit: int = MAX_BODY_CHARS) -> str:
    """Shorten a release body that is longer than ``limit`` characters.

    GitHub refuses a release body over 125,000 characters, and the release
    job would then publish no release and none of its signed assets. A body
    within ``limit`` is returned unchanged. A longer one keeps every section
    heading and its order: the last entries of the longest section are
    dropped, one at a time, until the body fits. Each shortened section ends
    with a line that counts the entries left out, and the body ends with a
    link to the full notes in the tagged CHANGELOG.md.

    Raises:
        ValueError: If the body cannot fit even with every entry dropped.
    """
    if len(body) <= limit:
        return body
    lead, sections = _split_sections(body)
    dropped = [0] * len(sections)
    full_notes = f"{CHANGELOG_URL.format(version=version)}"
    footer = (
        "\n---\n\nThese notes are shortened to fit GitHub's size limit for a "
        f"release page. The full notes are in [CHANGELOG.md]({full_notes}).\n"
    )

    def render() -> str:
        parts = list(lead)
        for (head, entries), cut in zip(sections, dropped, strict=True):
            parts.extend(head)
            for entry in entries:
                parts.extend(entry)
            if cut:
                if parts and parts[-1].strip():
                    parts.append("")
                parts.append(
                    f"- {cut} more {'entry' if cut == 1 else 'entries'} in the full notes."
                )
                parts.append("")
        return "\n".join(parts).strip() + "\n" + footer

    text = render()
    while len(text) > limit:
        sizes = [
            sum(len(line) + 1 for e in entries for line in e) for _, entries in sections
        ]
        if not any(sizes):
            raise ValueError(
                f"the [{version}] notes do not fit in {limit} characters "
                "even with every entry left out"
            )
        biggest = sizes.index(max(sizes))
        sections[biggest][1].pop()
        dropped[biggest] += 1
        text = render()
    return text


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
        body = fit_to_limit(extract_section(text, args.version), args.version)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    args.output.write_text(body, encoding="utf-8")
    print(f"wrote {len(body)} characters to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
