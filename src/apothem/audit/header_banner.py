# SPDX-License-Identifier: MIT

"""Why this module exists — one authority on what a canonical header looks like.

The scanner, the conformity validator, and the injector must agree byte-for-byte
on the canonical header, or a file one of them calls correct another calls
malformed. They deliberately do not share a module — each is independently
runnable — so they instead mirror the same rendering logic. This module is the
audit side of that mirror, held apart from the scanning that consumes it so the
rendering rules stay readable on their own.

Scope. Loads the single-line SPDX fixture at ``src/apothem/schemas/`` once at
import, then renders it into any comment-variant family: marker substitution
for the line-comment families (hash / double-slash / semicolon / double-dash)
and wrapper composition for the block families (html / c-block).

Detection strategy note. The fixture is resolved at import rather than per
call, because every caller renders against the same fixture and a per-call read
would make a hot scan re-read one small file thousands of times. An absent or
malformed fixture yields empty strings rather than raising — the caller treats
the empty result as "skip this check" instead of failing the whole scan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from apothem.audit.header_vocabulary import (
    SPDX_PREFIX_TEXT,
    VARIANT_C_BLOCK,
    VARIANT_DOUBLE_DASH,
    VARIANT_DOUBLE_SLASH,
    VARIANT_HASH,
    VARIANT_HTML,
    VARIANT_SEMICOLON,
)


def _replace_marker(line: str, source: str, target: str) -> str:
    """Substitute the leading comment marker on a header line.

    The narrowed header line carries the comment marker on its leading edge
    only; this swaps that edge. Mirrors scripts/inject-header.py and
    file_header_grep.py to preserve injector / validator / scanner parity.
    """
    if not line.startswith(source):
        return line
    if len(line) >= 2 * len(source) and line.endswith(source):
        inner = line[len(source) : -len(source)]
        return f"{target}{inner}{target}"
    return target + line[len(source) :]


def _render_variant(hash_form_line: str, spdx_text: str, variant: str) -> list[str]:
    """Render the canonical SPDX header line for ``variant``.

    Post-conditions: the returned list carries exactly one line and no
    trailing blank. Raises ``ValueError`` on a non-renderable family — an
    exempt file has no canonical form, so the caller filters it first.
    """
    if variant == VARIANT_HASH:
        return [hash_form_line]
    if variant == VARIANT_DOUBLE_SLASH:
        return [_replace_marker(hash_form_line, "#", "//")]
    if variant == VARIANT_SEMICOLON:
        return [_replace_marker(hash_form_line, "#", ";")]
    if variant == VARIANT_DOUBLE_DASH:
        return [_replace_marker(hash_form_line, "#", "--")]
    if variant == VARIANT_HTML:
        return [f"<!-- {spdx_text} -->"]
    if variant == VARIANT_C_BLOCK:
        return [f"/* {spdx_text} */"]
    raise ValueError(f"variant not renderable: {variant!r}")


def _render_canonical_block(
    hash_form_line: str, spdx_text: str, variant: str
) -> list[str]:
    """Render the canonical block including the mandatory trailing blank line."""
    return [*_render_variant(hash_form_line, spdx_text, variant), ""]


def _load_banner(schemas_dir: Path) -> tuple[str, str]:
    """Load the narrowed SPDX-line header fixture.

    Mirrors file_header_grep.py ``_load_banner``: the fixture is the single
    hash-form SPDX identifier line naming the MIT license. Returns
    ``(hash_form_line, spdx_text)`` on success, or two empty strings when the
    fixture is absent or malformed (the caller treats the empty result as a
    skip).

    The tag is described rather than quoted here on purpose: the REUSE
    scanner reads any occurrence of the literal tag in a file as that file's
    own license declaration, so spelling it out in prose made this module
    declare a malformed expression and failed the license gate.
    """
    banner_path = schemas_dir / "authorship-header.txt"
    if not banner_path.is_file():
        return "", ""
    raw = banner_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        return "", ""
    spdx_line = lines[0]
    if SPDX_PREFIX_TEXT not in spdx_line or not spdx_line.startswith("#"):
        return "", ""
    return spdx_line, spdx_line[1:].strip()


# Resolve the canonical header fixture once at import. The fixture lives at
# src/apothem/schemas/ relative to this file (audit/ → apothem/ → schemas/).
_SCHEMAS_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "schemas"
_HASH_FORM_LINE, _SPDX_TEXT = _load_banner(_SCHEMAS_DIR)


def canonical_banner_lines(variant: str) -> list[str]:
    """Return the canonical header lines for ``variant``.

    The narrowed header is a single line per variant. Raises ``ValueError``
    if ``variant`` is not a renderable family; the caller filters exempt
    files before requesting a canonical form.
    """
    return _render_variant(_HASH_FORM_LINE, _SPDX_TEXT, variant)


def canonical_banner_text(variant: str) -> str:
    """Return the canonical header as one newline-terminated text block.

    Kept alongside :func:`canonical_banner_lines` because a caller writing the
    header to disk wants the joined text while a caller comparing it against a
    file head wants the lines; joining at each call site invited drift in the
    line terminator.
    """
    return "\n".join(canonical_banner_lines(variant)) + "\n"


def canonical_block_lines(variant: str) -> list[str]:
    """Return the canonical header for ``variant`` plus its trailing blank.

    Why this exists alongside :func:`canonical_banner_lines`: the header
    contract is "the SPDX line, then one blank line", so a caller comparing a
    file head against the canonical form needs the blank while a caller
    rendering the line alone does not. Exposing both keeps the loaded fixture
    private to this module rather than making callers pass it back in.
    """
    return _render_canonical_block(_HASH_FORM_LINE, _SPDX_TEXT, variant)
