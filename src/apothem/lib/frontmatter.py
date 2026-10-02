# SPDX-License-Identifier: MIT

"""YAML frontmatter field probing and value extraction for ecosystem files.

Provides three layers of inspection:

* :func:`extract_frontmatter` — return the raw YAML block.
* :func:`field_value` — return the value of a single declared field as a string,
  or ``None`` when the field is absent (:func:`field_value_in_text` reads
  in-memory text instead of a file).
* :func:`has_field` / :func:`has_all_fields` — boolean presence checks.
* :func:`split_frontmatter` — split text into a byte-0 frontmatter block and
  the remainder, for emitters that must keep frontmatter first.

The probe is intentionally regex-based rather than a full YAML parser so that
the validator surface has zero third-party dependencies and remains
import-time cheap. It supports the small subset of YAML actually used in
ecosystem frontmatter: scalar values (quoted or unquoted) on a single line.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_FRONTMATTER_BLOCK: Final[re.Pattern[str]] = re.compile(
    r"\A---\s*\n(.*?)\n---", re.DOTALL
)
_LEADING_HTML_COMMENT: Final[re.Pattern[str]] = re.compile(
    r"\A\s*<!--.*?-->\s*", re.DOTALL
)
#: A YAML frontmatter block that opens at byte 0 and closes on its own
#: ``---`` line, including that line's newline when present.
_LEADING_FRONTMATTER: Final[re.Pattern[str]] = re.compile(
    r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL
)


def split_frontmatter(text: str) -> tuple[str, str] | None:
    """Split *text* into its byte-0 frontmatter block and the remainder.

    Unlike :func:`extract_frontmatter`, nothing may precede the opening
    ``---``: this is the strict shape harnesses such as Kiro and Cursor require
    for a rule file's activation keys. The returned block keeps both delimiter
    lines and the closing line's newline, so ``block + rest == text``.

    Returns:
        ``(block, rest)``, or ``None`` when *text* does not open with a
        frontmatter block.
    """
    match = _LEADING_FRONTMATTER.match(text)
    if match is None:
        return None
    return match.group(0), text[match.end() :]


def extract_frontmatter(path: Path) -> str | None:
    """Return the raw YAML block at the top of ``path``, or ``None``.

    A leading HTML-comment block (the canonical SPDX header line injected
    ecosystem-wide above the YAML frontmatter on every Markdown file) is
    skipped before matching the frontmatter delimiter so the probe sees
    the YAML block at the correct anchor.

    Args:
        path: File to read.

    Returns:
        The block content between the opening and closing ``---`` lines, or
        ``None`` when the file is unreadable or has no frontmatter.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return _frontmatter_block(text)


def _frontmatter_block(text: str) -> str | None:
    """Return the YAML block of *text*, skipping one leading HTML comment."""
    text = _LEADING_HTML_COMMENT.sub("", text, count=1)
    match = _FRONTMATTER_BLOCK.match(text)
    return match.group(1) if match else None


def field_value(path: Path, field_name: str) -> str | None:
    """Return the unquoted scalar value of ``field_name`` from ``path``.

    Recognizes single-line ``key: "value"`` and ``key: value`` declarations.
    Multi-line YAML constructs (block scalars, lists, mappings) return the
    raw matched suffix and should be treated as opaque by callers.

    Args:
        path: File to read.
        field_name: YAML key to look up.

    Returns:
        Stripped, dequoted value, or ``None`` when the field is absent.
    """
    return _block_field_value(extract_frontmatter(path), field_name)


def field_value_in_text(text: str, field_name: str) -> str | None:
    """Return the value of ``field_name`` from the frontmatter of *text*.

    The in-memory twin of :func:`field_value`, for emitters that hold rendered
    text rather than a source path. Same parsing rules and return contract.
    """
    return _block_field_value(_frontmatter_block(text), field_name)


def _block_field_value(block: str | None, field_name: str) -> str | None:
    """Return the dequoted scalar value of ``field_name`` in a YAML *block*."""
    if block is None:
        return None
    pattern = re.compile(
        rf"^{re.escape(field_name)}\s*:\s*(.*?)\s*$",
        re.MULTILINE,
    )
    match = pattern.search(block)
    if match is None:
        return None
    raw = match.group(1).strip()
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        # Dequote by stripping the outer quotes only. Backslash escape
        # sequences inside a double-quoted scalar (``"a \"b\""``) are NOT
        # decoded — the inner text is returned verbatim. Apothem's own
        # frontmatter values are plain prose with no escaped quotes, so this
        # is sufficient in practice; a value needing escape decoding must be
        # parsed with a full YAML loader by the caller.
        return raw[1:-1]
    return raw


def has_field(path: Path, field_name: str) -> bool:
    """Return True when frontmatter in ``path`` declares ``field_name:``."""
    return field_value(path, field_name) is not None


def has_all_fields(path: Path, field_names: list[str]) -> bool:
    """Return True when every field in ``field_names`` is declared."""
    return all(has_field(path, name) for name in field_names)
