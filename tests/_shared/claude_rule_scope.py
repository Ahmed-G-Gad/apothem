# SPDX-License-Identifier: MIT

"""When Claude Code loads a rule file, and which paths a rule glob matches.

Two behaviors of Claude Code decide what a ``~/.claude/rules/*.md`` copy costs a
session, and the unit tests need both as plain functions:

* **Launch.** A rule loads at launch when its frontmatter has no ``paths``
  list, and also when the list is unconditional: after each entry loses a
  trailing ``/**`` and the empty entries are dropped, nothing is left or every
  entry is ``**``. A rule whose only glob is ``**`` therefore loads in every
  session even though it carries a ``paths`` line. Checking ``"paths" not in``
  the frontmatter misses that case.
* **Match.** A user-level rule's globs are matched against the path of the file
  being read or edited, relative to the working directory, with ``.gitignore``
  semantics: a pattern with no ``/`` matches at any depth, a leading ``/``
  anchors the pattern to the root, ``**/`` spans directories, and a pattern
  that matches a directory matches everything below it.

Both were read from the loader and the matcher in the Claude Code build of
2026-10-20. :func:`loads_at_launch` and :func:`matches` restate them.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from functools import cache

import yaml


def effective_globs(globs: Sequence[str]) -> list[str]:
    """Return *globs* as Claude Code reads them: no trailing ``/**``, no empties."""
    stripped = [glob[:-3] if glob.endswith("/**") else glob for glob in globs]
    return [glob for glob in stripped if glob]


def unconditional(globs: Sequence[str]) -> bool:
    """Return True when a ``paths`` list scopes nothing, so the rule loads at launch."""
    kept = effective_globs(globs)
    return not kept or all(glob == "**" for glob in kept)


def loads_at_launch(globs: Sequence[str] | None) -> bool:
    """Return True when a rule with this ``paths`` list loads in every session."""
    return not globs or unconditional(globs)


def rendered_paths(text: str) -> list[str] | None:
    """Return the ``paths`` list in the frontmatter of the rule *text*, or None."""
    assert text.startswith("---\n"), text[:80]
    loaded = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(loaded, dict)
    paths = loaded.get("paths")
    if paths is None:
        return None
    assert isinstance(paths, list)
    return [str(item) for item in paths]


def loads_at_launch_text(text: str) -> bool:
    """Return True when the rendered rule *text* loads in every session."""
    return loads_at_launch(rendered_paths(text))


@cache
def _regex(pattern: str) -> re.Pattern[str]:
    """Translate one ``.gitignore``-style glob to a regex over a relative path."""
    anchored = "/" in pattern.rstrip("/")
    body = pattern.lstrip("/")
    out: list[str] = []
    i = 0
    while i < len(body):
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("/**", i) and i + 3 == len(body):
            out.append("/.*")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif body[i] == "*":
            out.append("[^/]*")
            i += 1
        elif body[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(body[i]))
            i += 1
    prefix = "" if anchored else "(?:.*/)?"
    return re.compile(prefix + "".join(out) + r"\Z")


def matches(patterns: Sequence[str], path: str) -> bool:
    """Return True when any of *patterns* matches *path* or a directory above it."""
    parts = path.split("/")
    candidates = ["/".join(parts[:end]) for end in range(1, len(parts) + 1)]
    return any(
        _regex(pattern).match(candidate)
        for pattern in patterns
        for candidate in candidates
    )
