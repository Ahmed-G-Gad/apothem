# SPDX-License-Identifier: MIT

"""Why this module exists — how a plan file earns its filename.

A plan file arrives with whatever name its author typed. The provenance
pipeline proposes a canonical one instead: a date, two hyphens, and a slug
derived from the strongest title the file offers. Three small decisions
make that up, and the pipeline needs the answer without needing the
reasoning behind it.

The title precedence is the load-bearing part. A declared frontmatter title
outranks the rendered H1, because frontmatter is an explicit authoring
decision while a heading is a rendering detail that may have drifted from
it. The filename stem is the last resort, because it is the very thing
being replaced.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from apothem.audit.plan_frontmatter import strip_frontmatter

_H1_RE: Final[re.Pattern[str]] = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def kebab_slug(text: str) -> str:
    """Reduce free text to a filename-safe kebab-case slug.

    Punctuation is dropped rather than transliterated, runs of whitespace
    and underscores collapse to a single hyphen, and the result is cut at
    60 characters so a verbose title cannot produce an unwieldy filename.
    Text that reduces to nothing comes back empty; the caller decides the
    fallback.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:60]


def h1_of(content: str) -> str | None:
    """Return the first level-one heading in the body, if there is one.

    The frontmatter block is stripped first, so a ``title:`` field cannot
    be mistaken for a heading and a ``---`` fence cannot end up in the
    match.
    """
    body = strip_frontmatter(content)
    match = _H1_RE.search(body)
    return match.group(1).strip() if match else None


def proposed_filename(
    path: Path,
    mtime_iso: str,
    fm_fields: dict[str, str],
    h1: str | None,
) -> str:
    """Compose the canonical ``<date>--<slug>.md`` name for a plan file.

    The date comes from the frontmatter ``created`` field when that field
    opens with an ISO calendar date, and from the file's modification time
    otherwise — a value the pattern cannot read is treated as absent rather
    than as an error. Only the date component survives, so a full timestamp
    contributes its first ten characters.

    The slug follows the title precedence described in the module
    docstring.
    """
    date_str = fm_fields.get("created", "")
    iso10 = re.match(r"\d{4}-\d{2}-\d{2}", date_str)
    date = iso10.group(0) if iso10 else mtime_iso[:10]
    if "title" in fm_fields:
        slug = kebab_slug(fm_fields["title"])
    elif h1:
        slug = kebab_slug(h1)
    else:
        slug = kebab_slug(path.stem)
    return f"{date}--{slug}.md"
