# SPDX-License-Identifier: MIT

"""Fold Apothem's extra frontmatter keys under ``metadata`` for Claude Code.

Claude Code ignores frontmatter keys it does not know, and the Agent Skills
standard keeps client-specific extras in a ``metadata`` map of strings
(https://code.claude.com/docs/en/skills, retrieved 2026-10-24). The source
corpus carries ``version``, ``updated``, ``archetype`` and ``portability`` at
the top level; the Claude Code emission moves them into a trailing
``metadata:`` map in a fixed order so the top level holds only keys Claude
Code reads.

The fold is line-based, like :func:`split_frontmatter`'s other users: it
touches only unindented ``key:`` lines inside the byte-0 frontmatter block and
leaves every other line, and the body, byte-identical.
"""

from __future__ import annotations

import json
from typing import Final

from apothem.lib.frontmatter import split_frontmatter

#: Top-level source keys folded under ``metadata``, in their emitted order.
METADATA_KEYS: Final[tuple[str, ...]] = (
    "version",
    "updated",
    "archetype",
    "portability",
)

#: First characters of a YAML value that is not a one-line scalar. Such a value
#: (a block scalar, flow collection, anchor, alias or tag) cannot become a
#: string-map entry without a YAML parser, so it stays at the top level.
_NON_SCALAR_STARTS: Final[str] = "|>[{&*!"

_INDENT: Final[tuple[str, str]] = (" ", "\t")


def _quoted_value(raw: str) -> str | None:
    """Return *raw* as a one-line double-quoted YAML string, or ``None``.

    ``None`` means the value is empty or not a one-line scalar and must stay
    where it is. A bare value such as the date ``2026-10-02`` is quoted so it
    reads back as a string, as the ``metadata`` map requires.
    """
    if not raw or raw[0] in _NON_SCALAR_STARTS:
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return raw
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return json.dumps(raw[1:-1].replace("''", "'"), ensure_ascii=False)
    return json.dumps(raw, ensure_ascii=False)


def fold_apothem_metadata(text: str) -> str:
    """Return *text* with the Apothem keys folded under a ``metadata`` map.

    Moves each top-level key of :data:`METADATA_KEYS` into a trailing
    ``metadata:`` map placed just before the closing ``---``, in the fixed
    order of :data:`METADATA_KEYS`; the remaining keys keep their source order.
    Values become double-quoted strings. The fold is idempotent: text with no
    top-level fold key is returned unchanged.

    Raises:
        ValueError: A key would be folded but the frontmatter already has a
            top-level ``metadata`` key.
    """
    parts = split_frontmatter(text)
    if parts is None:
        return text
    block, rest = parts
    newline = "\n" if block.endswith("\n") else ""
    lines = block[: len(block) - len(newline)].split("\n")
    opening, inner, closing = lines[0], lines[1:-1], lines[-1]
    kept: list[str] = []
    found: dict[str, str] = {}
    for line in inner:
        key, sep, value = line.partition(":")
        if sep and key in METADATA_KEYS and not line.startswith(_INDENT):
            quoted = _quoted_value(value.strip())
            if quoted is not None:
                found[key] = quoted
                continue
        kept.append(line)
    if not found:
        return text
    if any(
        line.partition(":")[0] == "metadata" and not line.startswith(_INDENT)
        for line in kept
    ):
        raise ValueError("frontmatter already has a top-level metadata key")
    folded = [f"  {key}: {found[key]}" for key in METADATA_KEYS if key in found]
    out = [opening, *kept, "metadata:", *folded, closing]
    return "\n".join(out) + newline + rest
