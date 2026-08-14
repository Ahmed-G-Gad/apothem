# SPDX-License-Identifier: MIT

r"""Why this module exists — reading what a plan file says about itself.

A plan file may open with a YAML-ish frontmatter block declaring its project,
title, and creation date. Two questions follow from that block and nothing
else in the provenance pipeline needs to know how either is answered: what did
the author declare, and where does the prose actually start.

Scope. The frontmatter grammar and the two readers over it. The patterns stay
private to this module because they are the grammar, not the contract; the
functions are public because other stages import them.

Note the asymmetry in the grammar: the block is only recognised at the very
start of the file (``\A``), so a ``---`` fence appearing later in the document
is body text. That keeps a horizontal rule mid-document from being mistaken
for metadata.
"""

from __future__ import annotations

import re
from typing import Final

_FRONTMATTER_RE: Final[re.Pattern[str]] = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)
_FRONTMATTER_PROJECT_RE: Final[re.Pattern[str]] = re.compile(
    r"^project:\s*(.+?)\s*$",
    re.MULTILINE,
)
_FRONTMATTER_TITLE_RE: Final[re.Pattern[str]] = re.compile(
    r"^title:\s*(.+?)\s*$",
    re.MULTILINE,
)
_FRONTMATTER_CREATED_RE: Final[re.Pattern[str]] = re.compile(
    r"^created:\s*(.+?)\s*$",
    re.MULTILINE,
)


def parse_frontmatter(content: str) -> dict[str, str]:
    """Lift the three tracked fields out of a leading frontmatter block.

    Only ``project``, ``title``, and ``created`` are read — the three the
    provenance pipeline acts on. Any other key in the block is left where it
    is rather than carried along, so the returned mapping is a decision
    surface and not a partial copy of the file's metadata.

    Content with no frontmatter yields an empty mapping, as does a block
    carrying none of the three; the caller cannot distinguish those cases
    and does not need to.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}
    body = match.group(1)
    fields: dict[str, str] = {}
    project = _FRONTMATTER_PROJECT_RE.search(body)
    if project:
        fields["project"] = project.group(1).strip()
    title = _FRONTMATTER_TITLE_RE.search(body)
    if title:
        fields["title"] = title.group(1).strip()
    created = _FRONTMATTER_CREATED_RE.search(body)
    if created:
        fields["created"] = created.group(1).strip()
    return fields


def strip_frontmatter(content: str) -> str:
    """Return the content with any leading frontmatter block removed.

    This is what lets a body scan treat the file as prose: without it a
    ``title:`` field would read as a heading candidate and the closing
    ``---`` fence as a horizontal rule. Content with no frontmatter comes
    back unchanged rather than trimmed.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return content
    return content[match.end() :]
