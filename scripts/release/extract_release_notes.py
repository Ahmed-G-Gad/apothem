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
    output path. A body longer than GitHub accepts for a release page is
    shortened first (see ``fit_to_limit``).

CLI:
    python scripts/release/extract_release_notes.py \\
        --version 1.2.3 \\
        --changelog CHANGELOG.md \\
        --output release-notes.md
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
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
    # LF only: str.splitlines() would also break a line at U+2028 or U+0085.
    lines = [line.removesuffix("\r") for line in changelog.split("\n")]

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


# A bold title in the plain shape the CHANGELOG uses, which CommonMark reads
# as bold: no '*', backslash, '<', '[', ']' or '|' inside, no space just
# inside the markers, and a space or the end after them. Other entries are
# dropped and counted, never cut to a title the input did not show.
_HEADLINE = re.compile(
    r"^(- \*\*[^\s*\\<\[\]|](?:[^*\\<\[\]|]*[^\s*\\<\[\]|])?\*\*)(?=\s|$)"
)
# A line that starts a new block (quote, list item, heading, table row), so
# the entry's first paragraph, and any title in it, ends before it.
_BLOCK_START = re.compile(r"^(?:[>#|]|[-*+](?:\s|$)|[0-9]{1,9}[.)](?:\s|$))")
# A GitHub table's delimiter row, such as '|---|:--:|'.
_TABLE_DELIMITER = re.compile(
    r"^\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?$|^\|\s*:?-+:?\s*\|$"
)
# '- - -' or '- ---' is a thematic break, not an entry, and ends the list.
_THEMATIC_BREAK = re.compile(r"^-(?: *-){2,} *$")
# A '===' or '---' line under an entry's text turns it into a heading.
_UNDERLINE = re.compile(r"^(?:=+|-+)$")
# CommonMark HTML blocks: kinds 1-6 can start anywhere; kind 7 (any other
# tag alone on its line) only after a blank line.
_HTML_ANYWHERE = re.compile(
    r"^<(?:!|\?|(?:script|pre|style|textarea)(?:\s|>|$)"
    r"|/?(?:address|article|aside|base|basefont|blockquote|body|caption|center"
    r"|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure"
    r"|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li"
    r"|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search"
    r"|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)"
    r"(?:\s|/?>|$))",
    re.IGNORECASE,
)
_HTML_TAG_LINE = re.compile(r"^</?[A-Za-z][A-Za-z0-9-]*(?:\s[^>]*)?/?>\s*$")
# Sections a reader must see whole: they are shortened only when no other
# section has anything left to shorten.
_PROTECTED = ("Security", "Data loss")


@dataclass
class _Entry:
    """One top-level ``- `` list entry with its indented continuation lines."""

    lines: list[str]
    short: bool = False

    def size(self) -> int:
        return sum(len(line) + 1 for line in self.lines)

    def headline(self) -> list[str] | None:
        """Return the entry cut to its bold title, or None when it cannot be."""
        if self.short:
            return None
        first: list[str] = []
        for line in self.lines:  # the entry's first paragraph only
            text = line.strip()
            if not text or (first and _BLOCK_START.match(text)):
                break
            first.append(text)
        match = _HEADLINE.match(" ".join(first))
        title = match.group(1) if match else ""
        if not title or title.count("`") % 2 or "``" in title:
            return None  # no plain bold title, or its '**' sits inside code
        blanks = 0
        for line in reversed(self.lines):
            if line.strip():
                break
            blanks += 1
        cut = [match.group(1), *([""] * blanks)]
        return cut if sum(len(line) + 1 for line in cut) < self.size() else None


@dataclass
class _Section:
    head: list[str]
    entries: list[_Entry] = field(default_factory=list)
    dropped: int = 0

    @property
    def protected(self) -> bool:
        return any(name in self.head[0] for name in _PROTECTED)


def _split_sections(body: str) -> tuple[list[str], list[_Section]]:
    """Split a release body into ``###`` sections of ``- `` entries.

    Only the exact shape the CHANGELOG uses can be shortened safely, so
    every non-blank line must be one of: a ``### `` heading, an entry line
    ``- `` followed by text, or a continuation line of an entry that starts
    with two ASCII spaces. A line of any other shape raises ValueError: text
    before the first heading, a ``####`` heading, a paragraph, another list
    marker or a wider ``-`` marker, a ``- - -`` thematic break, a line
    indented by one space or a non-ASCII space, any tab, and, even when
    indented, a code fence, an HTML line or a ``]:`` that may start a link
    reference definition, which could reach past the entry that holds it.
    The release page then never silently loses part of a section.
    """
    lead: list[str] = []
    sections: list[_Section] = []
    previous = ""
    # Split on LF only: str.splitlines() also breaks at U+2028, U+0085 and
    # other characters Markdown does not treat as line ends.
    for number, raw in enumerate(body.removesuffix("\n").split("\n"), start=1):
        line = raw.removesuffix("\r")
        stripped = line.strip()
        line_before, previous = previous, line
        if not stripped:
            if sections and sections[-1].entries:
                sections[-1].entries[-1].lines.append(line)
            elif sections:
                sections[-1].head.append(line)
            else:
                lead.append(line)
            continue
        if "\t" not in line and line.startswith("### ") and line[4:5] not in ("", " "):
            sections.append(_Section([line]))
            continue
        problem = None
        if "\t" in line or "\f" in line or "\v" in line:
            problem = "holds a tab or a page break"
        elif "]:" in line:
            problem = "may hold a link reference definition"
        elif _THEMATIC_BREAK.match(line):
            problem = "is a thematic break"
        elif not sections:
            problem = "comes before the first ### heading"
        elif _TABLE_DELIMITER.match(stripped):
            problem = "is a table delimiter row"
        elif _UNDERLINE.match(stripped):
            problem = "is a heading underline or a rule"
        elif stripped.lstrip("- ").startswith(("```", "~~~")):
            problem = "is a code fence"
        elif _HTML_ANYWHERE.match(stripped) or (
            not line_before.strip() and _HTML_TAG_LINE.match(stripped)
        ):
            problem = "starts an HTML block"
        elif line.startswith("- ") and line[2:3] not in ("", " "):
            sections[-1].entries.append(_Entry([line]))
        elif line.startswith("  ") and sections[-1].entries:
            sections[-1].entries[-1].lines.append(line)
        else:
            problem = "is not a '- ' entry or a two-space-indented line of one"
        if problem is not None:
            raise ValueError(f"line {number} {problem}: {line!r}")
    return lead, sections


def _render(lead: list[str], sections: list[_Section], footer: str) -> str:
    parts = list(lead)
    for section in sections:
        parts.extend(section.head)
        for entry in section.entries:
            parts.extend(entry.lines)
        if section.dropped:
            if parts and parts[-1].strip():
                parts.append("")
            cut = section.dropped
            noun = "entry" if cut == 1 else "entries"
            parts.append(f"- {cut} more {noun} in the full notes.")
            parts.append("")
    return "\n".join(parts).strip() + "\n" + footer


def _shorten_one(sections: list[_Section]) -> bool:
    """Shorten the body by one step; return False when nothing is left.

    The first steps cut entries to their bold titles, last entry first, in
    the section with the most text left to cut. Only when no entry can be
    cut to a title are whole entries dropped, the same way. The Security and
    data-loss sections are touched only after every other section is done.
    """
    for protected in (False, True):
        pool = [s for s in sections if s.protected == protected]
        cuts = [
            sum(e.size() for e in s.entries if e.headline() is not None) for s in pool
        ]
        if any(cuts):
            section = pool[cuts.index(max(cuts))]
            for entry in reversed(section.entries):
                title = entry.headline()
                if title is not None:
                    entry.lines = title
                    entry.short = True
                    return True
    for protected in (False, True):
        pool = [s for s in sections if s.protected == protected]
        sizes = [sum(e.size() for e in s.entries) for s in pool]
        if any(sizes):
            section = pool[sizes.index(max(sizes))]
            section.entries.pop()
            section.dropped += 1
            return True
    return False


def _github_length(text: str) -> int:
    """The longer of the text's code points and UTF-16 units, CRLF counted."""
    crlf = text.count("\n") - text.count("\r\n")
    return max(len(text), len(text.encode("utf-16-le")) // 2) + crlf


def fit_to_limit(body: str, version: str, limit: int = MAX_BODY_CHARS) -> str:
    """Shorten a release body that is longer than ``limit`` characters.

    GitHub refuses a release body over 125,000 characters, and the release
    job would then publish no release and none of its signed assets. A body
    within ``limit`` is returned unchanged. A longer one keeps every section
    heading and its order. Entries are first cut to their bold titles, and
    only then dropped, each time from the end of the section with the most
    text; the Security and data-loss sections come last. A section that lost
    entries ends with a line that counts them, and the body ends with a link
    to the full notes in the tagged CHANGELOG.md.

    Raises:
        ValueError: If the body cannot fit even with every entry dropped, or
            a section that must be shortened has a shape other than ``- ``
            entries (see ``_split_sections``).
    """
    if _github_length(body) <= limit:
        return body
    try:
        lead, sections = _split_sections(body)
    except ValueError as exc:
        raise ValueError(
            f"the [{version}] notes are too long for a release page and cannot be "
            f"shortened safely: {exc}. Change that line, or shorten the notes by hand"
        ) from exc
    full_notes = CHANGELOG_URL.format(version=version)
    footer = (
        "\n---\n\nThese notes are shortened to fit GitHub's size limit for a "
        "release page: some entries show only their title, and some may be "
        f"left out. The full notes are in [CHANGELOG.md]({full_notes}).\n"
    )
    text = _render(lead, sections, footer)
    while _github_length(text) > limit:
        if not _shorten_one(sections):
            raise ValueError(
                f"the [{version}] notes do not fit in {limit} characters "
                "even with every entry left out"
            )
        text = _render(lead, sections, footer)
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
