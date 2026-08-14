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
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return content
    return content[match.end() :]
