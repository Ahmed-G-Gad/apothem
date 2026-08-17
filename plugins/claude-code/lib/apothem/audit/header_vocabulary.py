# SPDX-License-Identifier: MIT

"""Why this vocabulary exists — the shared nouns of header coverage.

The header-coverage pipeline is four concerns wide: it resolves a file's
comment-variant family, detects whether a canonical SPDX line is present,
classifies how a present-but-wrong header is malformed, and reports the
result. Those four stages disagree about almost everything except the *names*
they use — ``present-canonical``, ``hash``, ``wrong-variant``. Holding those
names in the scanner module coupled every stage to the scanner; holding them
here lets each stage import the vocabulary without importing its siblings.

Scope. Pure data: the four-value header-status taxonomy, the seven
comment-variant families, the eight malformation classes, the suffix and
basename maps that resolve a path to its variant, the marker text the detector
greps for, and the scan budgets and exit codes. No behavior lives here — a
function that *interprets* these constants belongs to the stage that owns the
interpretation.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Header-status taxonomy. Mirrors the inventory's four-value taxonomy.
# ---------------------------------------------------------------------------
HEADER_PRESENT_CANONICAL: Final[str] = "present-canonical"
HEADER_PRESENT_MALFORMED: Final[str] = "present-malformed"
HEADER_ABSENT: Final[str] = "absent"
HEADER_NOT_APPLICABLE: Final[str] = "not-applicable"

ALL_HEADER_STATUSES: Final[tuple[str, ...]] = (
    HEADER_PRESENT_CANONICAL,
    HEADER_PRESENT_MALFORMED,
    HEADER_ABSENT,
    HEADER_NOT_APPLICABLE,
)

# ---------------------------------------------------------------------------
# Variant-family taxonomy per spec §4.6.2.
# ---------------------------------------------------------------------------
VARIANT_HASH: Final[str] = "hash"
VARIANT_DOUBLE_SLASH: Final[str] = "double-slash"
VARIANT_HTML: Final[str] = "html"
VARIANT_C_BLOCK: Final[str] = "c-block"
VARIANT_SEMICOLON: Final[str] = "semicolon"
VARIANT_DOUBLE_DASH: Final[str] = "double-dash"
VARIANT_EXEMPT: Final[str] = "exempt"

ALL_VARIANTS: Final[tuple[str, ...]] = (
    VARIANT_HASH,
    VARIANT_DOUBLE_SLASH,
    VARIANT_HTML,
    VARIANT_C_BLOCK,
    VARIANT_SEMICOLON,
    VARIANT_DOUBLE_DASH,
    VARIANT_EXEMPT,
)

# ---------------------------------------------------------------------------
# Header-malformation taxonomy consumed by the coverage scanner.
# ---------------------------------------------------------------------------
MALFORM_WRONG_VARIANT: Final[str] = "wrong-variant"
MALFORM_WRONG_LINE_ORDER: Final[str] = "wrong-line-order"
MALFORM_DRIFTED_CONTACT: Final[str] = "drifted-contact-info"
MALFORM_SMART_QUOTE: Final[str] = "smart-quote-pollution"
MALFORM_BOM_PREFIX: Final[str] = "bom-prefix"
MALFORM_TRAILING_WHITESPACE: Final[str] = "trailing-whitespace"
MALFORM_WRONG_LINE_COUNT: Final[str] = "wrong-line-count"
MALFORM_MIXED: Final[str] = "mixed"

ALL_MALFORMATIONS: Final[tuple[str, ...]] = (
    MALFORM_WRONG_VARIANT,
    MALFORM_WRONG_LINE_ORDER,
    MALFORM_DRIFTED_CONTACT,
    MALFORM_SMART_QUOTE,
    MALFORM_BOM_PREFIX,
    MALFORM_TRAILING_WHITESPACE,
    MALFORM_WRONG_LINE_COUNT,
    MALFORM_MIXED,
)

# ---------------------------------------------------------------------------
# Variant-family resolution per spec §4.6.2.
#
# The mapping is consulted by suffix (lowercase) first; basename overrides
# follow for files with no suffix or with a name-only convention
# (Makefile, Dockerfile, etc.). Files whose suffix is not registered fall
# to ``exempt`` — the exception fixture is the authoritative gate, so a
# fall-through here only matters when the path also escapes the fixture.
# ---------------------------------------------------------------------------
SUFFIX_VARIANT: Final[dict[str, str]] = {
    # `#` family
    ".sh": VARIANT_HASH,
    ".bash": VARIANT_HASH,
    ".zsh": VARIANT_HASH,
    ".py": VARIANT_HASH,
    ".rb": VARIANT_HASH,
    ".pl": VARIANT_HASH,
    ".ps1": VARIANT_HASH,
    ".psm1": VARIANT_HASH,
    ".psd1": VARIANT_HASH,
    ".yml": VARIANT_HASH,
    ".yaml": VARIANT_HASH,
    ".toml": VARIANT_HASH,
    ".cff": VARIANT_HASH,
    ".gitignore": VARIANT_HASH,
    ".gitattributes": VARIANT_HASH,
    ".editorconfig": VARIANT_HASH,
    ".shellcheckrc": VARIANT_HASH,
    ".env.example": VARIANT_HASH,
    ".cfg": VARIANT_HASH,
    ".conf": VARIANT_HASH,
    # `//` family
    ".js": VARIANT_DOUBLE_SLASH,
    ".jsx": VARIANT_DOUBLE_SLASH,
    ".mjs": VARIANT_DOUBLE_SLASH,
    ".cjs": VARIANT_DOUBLE_SLASH,
    ".ts": VARIANT_DOUBLE_SLASH,
    ".tsx": VARIANT_DOUBLE_SLASH,
    ".go": VARIANT_DOUBLE_SLASH,
    ".rs": VARIANT_DOUBLE_SLASH,
    ".java": VARIANT_DOUBLE_SLASH,
    ".kt": VARIANT_DOUBLE_SLASH,
    ".swift": VARIANT_DOUBLE_SLASH,
    ".scala": VARIANT_DOUBLE_SLASH,
    ".dart": VARIANT_DOUBLE_SLASH,
    ".cs": VARIANT_DOUBLE_SLASH,
    ".jsonc": VARIANT_DOUBLE_SLASH,
    # block-comment family (HTML-style wrapper)
    ".html": VARIANT_HTML,
    ".htm": VARIANT_HTML,
    ".md": VARIANT_HTML,
    ".markdown": VARIANT_HTML,
    ".mdc": VARIANT_HTML,
    ".xml": VARIANT_HTML,
    ".vue": VARIANT_HTML,
    ".php": VARIANT_HTML,
    # `/* */` block family
    ".c": VARIANT_C_BLOCK,
    ".cc": VARIANT_C_BLOCK,
    ".cpp": VARIANT_C_BLOCK,
    ".h": VARIANT_C_BLOCK,
    ".hpp": VARIANT_C_BLOCK,
    ".css": VARIANT_C_BLOCK,
    ".scss": VARIANT_C_BLOCK,
    ".less": VARIANT_C_BLOCK,
    ".sql": VARIANT_DOUBLE_DASH,
    # `;` family
    ".ini": VARIANT_SEMICOLON,
    ".lisp": VARIANT_SEMICOLON,
    ".scm": VARIANT_SEMICOLON,
    # `--` family
    ".lua": VARIANT_DOUBLE_DASH,
    ".hs": VARIANT_DOUBLE_DASH,
    ".elm": VARIANT_DOUBLE_DASH,
    ".ada": VARIANT_DOUBLE_DASH,
}

BASENAME_VARIANT: Final[dict[str, str]] = {
    "Makefile": VARIANT_HASH,
    "Dockerfile": VARIANT_HASH,
    "Procfile": VARIANT_HASH,
    "CODEOWNERS": VARIANT_HASH,
    "apothem": VARIANT_HASH,
    "PKGBUILD": VARIANT_HASH,
    ".gitignore": VARIANT_HASH,
    ".gitattributes": VARIANT_HASH,
    ".editorconfig": VARIANT_HASH,
    ".shellcheckrc": VARIANT_HASH,
    ".env.example": VARIANT_HASH,
}

# ---------------------------------------------------------------------------
# Canonical header — the single SPDX-License-Identifier line (D-007).
#
# The header was narrowed from a six-line branded banner box to one
# machine-readable license-identifier line per comment-syntax variant.
# Only comment syntax varies between variants; the identifier text is
# invariant. Drift in the identifier line is a CI failure.
#
# SPDX_PREFIX_TEXT is the substring that identifies the SPDX line in any
# variant. LEGACY_AUTHOR_MARK is retained purely as a detection constant:
# a file still carrying the retired branded-banner author line (but not the
# narrowed SPDX line at the canonical site) is a not-yet-narrowed header and
# is counted malformed/uncovered, so the scan surfaces the remaining work.
# ---------------------------------------------------------------------------
# Composed rather than written as one literal: the REUSE scanner treats any
# contiguous occurrence of the tag in a file as that file's own license
# declaration, and parses whatever follows as the expression. Spelling it out
# here made this module declare `"` as its license and failed the license gate.
# Splitting the literal keeps the runtime value identical while leaving no
# contiguous tag for the scanner to misread.
_SPDX_TAG_HEAD: Final[str] = "SPDX-License"
SPDX_PREFIX_TEXT: Final[str] = f"{_SPDX_TAG_HEAD}-Identifier:"
LEGACY_AUTHOR_MARK: Final[str] = "Copyright (c) Ahmed G. Gad"

# Smart-quote codepoints whose presence inside a banner is malformation
# class ``smart-quote-pollution``. Source-escaped so the
# scanner's own bytes never trigger the ambiguous-Unicode lint rule
# that would otherwise flag literal smart quotes.
SMART_QUOTES: Final[tuple[str, ...]] = (
    "‘",  # noqa: RUF001 - detection codepoint U+2018
    "’",  # noqa: RUF001 - detection codepoint U+2019
    "“",
    "”",
    "–",  # noqa: RUF001 - detection codepoint U+2013
    "—",
)

BOM_PREFIX: Final[str] = "﻿"

# Number of leading lines scanned for banner detection. Must accommodate
# shebang + (optional) interpreter-pragma + frontmatter + banner shape.
SCAN_LINE_BUDGET: Final[int] = 60

# Per-file unified-diff context lines. Three lines is unified-diff
# default; the injection-plan diff uses a tighter window because the
# patch is always at the head of the file.
DIFF_CONTEXT_LINES: Final[int] = 3

EXIT_OK: Final[int] = 0
EXIT_ERROR: Final[int] = 1
