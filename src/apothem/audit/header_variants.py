# SPDX-License-Identifier: MIT

"""Why this module exists — deciding whether a file needs a header, and which.

Two questions precede any header check, and neither is about headers. First:
which comment syntax does this filetype use, since a ``.py`` file and a ``.md``
file carry the same license line behind different markers. Second: is this file
even in scope, since vendored trees, generated output, and binary assets are
exempt by fixture rather than by inspection.

Both are path questions answered before a single byte of the file is read, so
they live apart from the detection and reporting stages that consume them.

Scope. Suffix and basename resolution to a comment-variant family, parsing of
the exception fixture, and the glob matcher that decides membership. The
matcher extends ``fnmatch`` with ``**`` cross-segment semantics, because the
fixture is authored in the conventional gitignore dialect that ``fnmatch``
alone does not implement.
"""

from __future__ import annotations

import re
from pathlib import Path

from apothem.audit.header_vocabulary import (
    BASENAME_VARIANT,
    SUFFIX_VARIANT,
    VARIANT_EXEMPT,
)


def variant_family_for(relative_path: Path) -> str:
    """Resolve the canonical variant family for the file's filetype.

    Suffix lookup is the primary signal; basename overrides cover
    suffix-less artifacts (Makefile / Dockerfile / dotfiles whose
    name encodes the convention). When neither resolves, the file is
    treated as ``exempt`` — the exception fixture remains the
    authoritative applicability gate, so a fall-through here only
    matters for files the fixture also fails to cover.
    """
    name = relative_path.name
    if name in BASENAME_VARIANT:
        return BASENAME_VARIANT[name]

    suffix = relative_path.suffix.lower()
    if suffix in SUFFIX_VARIANT:
        return SUFFIX_VARIANT[suffix]

    return VARIANT_EXEMPT


# ---------------------------------------------------------------------------
# Exception-fixture parsing.
# ---------------------------------------------------------------------------
def load_exception_globs(fixture_path: Path) -> list[str]:
    """Parse ``src/apothem/schemas/header-exceptions.txt`` into a glob list.

    Comment lines (``#``-prefixed) and blank lines are stripped; every
    other line becomes a pathspec. The order is preserved so a future
    deny-list / allow-list extension can rely on first-match semantics.
    """
    if not fixture_path.is_file():
        return []
    globs: list[str] = []
    for raw in fixture_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        globs.append(line)
    return globs


def matches_exception(relative_path: str, globs: list[str]) -> str | None:
    """Return the first matching glob, or ``None`` when the path is in scope.

    Patterns containing ``**`` are translated to fnmatch-friendly form by
    treating ``**`` as ``*`` across path separators (fnmatch handles
    cross-segment expansion when the path is expressed as POSIX-style).
    """
    posix = relative_path.replace("\\", "/")
    for pattern in globs:
        if _fnmatch_with_globstar(posix, pattern):
            return pattern
    return None


def _fnmatch_with_globstar(path: str, pattern: str) -> bool:
    """Return ``True`` when ``pattern`` matches ``path`` under fnmatch
    semantics extended for ``**`` cross-segment expansion.

    fnmatch alone treats ``*`` as non-greedy across separators; ``**``
    here matches zero or more path segments (the conventional gitignore
    /gitattributes / Unix glob semantics). Translation is deliberately
    direct — character-by-character regex synthesis with the four
    glob-significant tokens (``**``, ``*``, ``?``, character classes)
    handled inline; ordinary characters are escaped via ``re.escape``.
    """
    if (
        "**" not in pattern
        and "*" not in pattern
        and "?" not in pattern
        and "[" not in pattern
    ):
        return path == pattern

    regex_parts: list[str] = []
    i = 0
    pattern_length = len(pattern)
    while i < pattern_length:
        char = pattern[i]
        if char == "*":
            if i + 1 < pattern_length and pattern[i + 1] == "*":
                # `**` token. When followed by `/`, the segment is
                # optional — `**/foo` matches `foo` AND `a/foo`. When
                # standalone (e.g. trailing `**`), the token matches
                # any remaining suffix including empty.
                if i + 2 < pattern_length and pattern[i + 2] == "/":
                    regex_parts.append("(?:.*/)?")
                    i += 3
                    continue
                regex_parts.append(".*")
                i += 2
                continue
            # Single `*` — match within a segment only.
            regex_parts.append("[^/]*")
            i += 1
            continue
        if char == "?":
            regex_parts.append("[^/]")
            i += 1
            continue
        regex_parts.append(re.escape(char))
        i += 1

    full = "^" + "".join(regex_parts) + "$"
    return re.match(full, path) is not None
