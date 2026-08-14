# SPDX-License-Identifier: MIT

"""Why this module exists — turning Markdown into a per-section verdict.

An instruction surface is prose; the coherence pass needs structure. This is
the stage in between: it slices the document into headings with their bodies,
then decides, for each canonical section, whether that section is present,
absent, or present under a different name.

Scope. Pure functions over strings — no filesystem, no scan state. The heading
regex, the heading/body block model, the keyword and signature matchers, and
the presence verdict.

Detection strategy. Presence is decided in four ordered branches, and the
order carries the design: a matching heading wins outright, because the
heading *is* the canonical claim and a thin body only means the section is
under-fleshed. Only when no heading matches does a body signature promote the
section to ``renamed-to:<heading>``. A signature found outside every heading
reports ``renamed-to:<no-heading-found>`` rather than guessing an owner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from apothem.audit.ai_surface_catalog import (
    PRESENCE_ABSENT,
    PRESENCE_PRESENT,
    PRESENCE_RENAMED_PREFIX,
    CanonicalSection,
)

# ---------------------------------------------------------------------------
# Heading parsing. We extract every level-two heading and the body block
# that follows up to the next level-two heading.
# ---------------------------------------------------------------------------
HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class HeadingBlock:
    """One parsed heading plus the body block that follows it.

    ``line_start`` / ``line_end`` are 1-based and bound the body slice up to
    the next heading; ``level`` is the ``#`` depth.
    """

    level: int
    text: str
    line_start: int
    line_end: int
    body: str


def parse_headings(content: str) -> list[HeadingBlock]:
    """Return every heading paired with its body block.

    A heading's body extends from the line after the heading up to the
    line before the next heading at the same or shallower depth. We use
    a flat slice and the parser keeps every heading level so the
    section-presence heuristic can pick the most specific match.
    """
    lines = content.splitlines()
    matches: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match is None:
            continue
        level = len(match.group("hashes"))
        text = match.group("text").strip()
        matches.append((index, level, text))
    blocks: list[HeadingBlock] = []
    for position, (line_index, level, text) in enumerate(matches):
        start = line_index + 1
        if position + 1 < len(matches):
            next_line, _next_level, _ = matches[position + 1]
            end = next_line
        else:
            end = len(lines)
        body = "\n".join(lines[start:end])
        blocks.append(
            HeadingBlock(
                level=level,
                text=text,
                line_start=line_index + 1,
                line_end=end,
                body=body,
            )
        )
    return blocks


def heading_text_matches(text: str, keywords: tuple[str, ...]) -> bool:
    """Case-insensitive substring test against any one keyword."""
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def body_signature_count(body: str, signatures: tuple[str, ...]) -> int:
    """Count the distinct signature substrings present in a body block.

    Case-sensitive — banner text and modal verbs are case-meaningful.
    """
    return sum(1 for signature in signatures if signature in body)


def detect_section_presence(
    section: CanonicalSection,
    headings: list[HeadingBlock],
    full_content: str,
) -> str:
    """Return ``present`` / ``absent`` / ``renamed-to:<text>``.

    Order of preference:
    1. A heading whose text matches the section's keywords AND whose
       body carries at least one signature → ``present``.
    2. A heading whose text matches the keywords but whose body lacks a
       signature → still ``present`` (the heading is the canonical
       claim; signature absence may indicate an under-fleshed section
       but not a renamed section).
    3. No heading-text match, but a heading whose body carries at least
       one signature → ``renamed-to:<heading-text>``. The first such
       heading by document order wins.
    4. No heading-text match and no body-signature match anywhere →
       ``absent``.
    """
    for heading in headings:
        if heading_text_matches(heading.text, section.heading_keywords):
            return PRESENCE_PRESENT
    for heading in headings:
        if body_signature_count(heading.body, section.body_signatures) > 0:
            return f"{PRESENCE_RENAMED_PREFIX}{heading.text}"
    if body_signature_count(full_content, section.body_signatures) > 0:
        return f"{PRESENCE_RENAMED_PREFIX}<no-heading-found>"
    return PRESENCE_ABSENT
