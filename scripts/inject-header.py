#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Deterministic authorship-header injector.

Reads ``src/apothem/schemas/authorship-header.txt`` for the canonical banner,
``src/apothem/schemas/header-exceptions.txt`` for applicability, and
``src/apothem/schemas/header-visibility.yaml`` for the per-class Markdown visibility
policy. For each input file path resolves the variant family, detects
the existing header state (canonical / malformed / absent), and either
writes the canonical banner in-place, prints a unified diff, or exits
non-zero on any divergence.

Modes:
    fix-in-place: Writes corrections directly. Idempotent.
    emit-patch:   Prints unified diff to stdout. Read-only.
    check:        Exits non-zero on any divergence. Read-only. CI-suitable.

The canonical header (D-007 NARROW verdict) is the single machine-readable
``SPDX-License-Identifier: MIT`` line per the REUSE specification; the
bordered branded banner box is retired and the root ``LICENSE`` carries the
full copyright instrument. The hash-form reference rendering lives at
``src/apothem/schemas/authorship-header.txt`` (``# SPDX-License-Identifier: MIT``).
Per-filetype variants are derived deterministically: hash / double-slash /
semicolon / double-dash by leading-marker substitution; html as
``<!-- ... -->`` and c-block as ``/* ... */`` single-line wrappers. The
injector still recognises and strips the retired multi-line banner (keyed on
the legacy ``Copyright (c) ...`` author line) so a migration run reduces every
legacy header to the SPDX line in one idempotent pass.

Exit codes:
    0 — Success or no divergence found.
    1 — Divergence found in ``check`` mode.
    2 — Irrecoverable error (missing fixture, invalid argument).
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Variant families.
# ---------------------------------------------------------------------------

VARIANT_HASH: Final[str] = "hash"
VARIANT_DOUBLE_SLASH: Final[str] = "double-slash"
VARIANT_HTML: Final[str] = "html"
VARIANT_C_BLOCK: Final[str] = "c-block"
VARIANT_SEMICOLON: Final[str] = "semicolon"
VARIANT_DOUBLE_DASH: Final[str] = "double-dash"
VARIANT_EXEMPT: Final[str] = "exempt"

# Suffix → variant family. Mirrors the resolution table in
# ``src/apothem/audit/scan_header_coverage.py`` so the injector and the
# coverage scanner converge on identical applicability verdicts. Drift
# between the two tables is a CI failure surfaced by the file-header
# validator at the next phase.
SUFFIX_VARIANT: Final[dict[str, str]] = {
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
    ".cfg": VARIANT_HASH,
    ".conf": VARIANT_HASH,
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
    ".html": VARIANT_HTML,
    ".htm": VARIANT_HTML,
    ".md": VARIANT_HTML,
    ".markdown": VARIANT_HTML,
    ".mdc": VARIANT_HTML,
    ".xml": VARIANT_HTML,
    ".vue": VARIANT_HTML,
    ".php": VARIANT_HTML,
    ".c": VARIANT_C_BLOCK,
    ".cc": VARIANT_C_BLOCK,
    ".cpp": VARIANT_C_BLOCK,
    ".h": VARIANT_C_BLOCK,
    ".hpp": VARIANT_C_BLOCK,
    ".css": VARIANT_C_BLOCK,
    ".scss": VARIANT_C_BLOCK,
    ".less": VARIANT_C_BLOCK,
    ".sql": VARIANT_DOUBLE_DASH,
    ".ini": VARIANT_SEMICOLON,
    ".lisp": VARIANT_SEMICOLON,
    ".scm": VARIANT_SEMICOLON,
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
    ".cursorrules": VARIANT_HASH,
    ".windsurfrules": VARIANT_HASH,
}

# ---------------------------------------------------------------------------
# Fixture defaults & exit codes.
# ---------------------------------------------------------------------------

DEFAULT_BANNER_PATH: Final[str] = "src/apothem/schemas/authorship-header.txt"
DEFAULT_EXCEPTIONS_PATH: Final[str] = "src/apothem/schemas/header-exceptions.txt"

SCAN_LINE_BUDGET: Final[int] = 60

EXIT_OK: Final[int] = 0
EXIT_DIVERGENCE: Final[int] = 1
EXIT_ERROR: Final[int] = 2

MODE_FIX: Final[str] = "fix-in-place"
MODE_PATCH: Final[str] = "emit-patch"
MODE_CHECK: Final[str] = "check"
ALL_MODES: Final[tuple[str, ...]] = (MODE_FIX, MODE_PATCH, MODE_CHECK)

# Marker substring that anchors banner detection. Any line containing
# this substring within the scan budget is treated as the banner's
# Copyright line (the second information line in the new 6-line form;
# the first information line in the legacy 5-line form).
AUTHOR_MARK: Final[str] = "Copyright (c) Ahmed G. Gad"

# Marker substring that identifies the SPDX license-identifier line.
# Presence above ``AUTHOR_MARK`` distinguishes the new 6-line form
# (SPDX top + 5 contact lines) from the legacy 5-line form. The strip
# logic uses this to size the legacy block correctly without removing
# adjacent file content.
SPDX_PREFIX_TEXT: Final[str] = "SPDX-License-Identifier:"


# ---------------------------------------------------------------------------
# Banner parsing & rendering.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CanonicalBanner:
    """Parsed canonical header derivable into per-variant renderings.

    The NARROW header (D-007) is the single machine-readable
    ``SPDX-License-Identifier: MIT`` line per comment family; the bordered
    branded box (copyright / website / email / GitHub / license-pointer
    lines) is retired. The root ``LICENSE`` carries the full copyright
    instrument; the per-file header carries only the SPDX identifier the
    supply-chain / SBOM tooling consumes.

    Attributes:
        spdx_text: The SPDX information text without any comment marker
            (``"SPDX-License-Identifier: MIT"``).
        hash_form_line: The raw hash-form line from the fixture, preserved
            byte-exact (``# SPDX-License-Identifier: MIT``). The hash
            variant emits it directly; other variants are derived by
            marker substitution or wrapper synthesis.
    """

    spdx_text: str
    hash_form_line: str


def load_canonical_banner(banner_path: Path) -> CanonicalBanner:
    """Load and parse the canonical SPDX-line header fixture.

    Args:
        banner_path: Path to ``src/apothem/schemas/authorship-header.txt``.

    Returns:
        A ``CanonicalBanner`` carrying the SPDX information text and the
        raw hash-form line preserved byte-exact.

    Raises:
        FileNotFoundError: When ``banner_path`` does not exist.
        ValueError: When the fixture does not parse as a single hash-form
            ``# SPDX-License-Identifier: ...`` line.
    """
    if not banner_path.is_file():
        raise FileNotFoundError(f"banner fixture not found: {banner_path}")
    raw = banner_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(
            f"expected 1 SPDX header line in {banner_path}, found {len(lines)}",
        )
    spdx_line = lines[0]
    if SPDX_PREFIX_TEXT not in spdx_line or not spdx_line.startswith("#"):
        raise ValueError(
            f"expected SPDX-License-Identifier hash line, got: {spdx_line!r}",
        )
    return CanonicalBanner(
        spdx_text=spdx_line[1:].strip(),
        hash_form_line=spdx_line,
    )


def _replace_marker(line: str, source: str, target: str) -> str:
    """Substitute the comment marker on a banner line.

    Banner lines come in two shapes. **Bordered** lines (rows 2-6 of the
    canonical fixture) carry the marker on both leading and trailing
    edges (``#  Copyright (c) ...  #``); both edges swap together while
    preserving the inner content (including decorative dash runs)
    byte-for-byte. **Prefix-only** lines (row 1, the SPDX line) carry
    the marker only on the leading edge (``# SPDX-License-Identifier: MIT``);
    only the leading edge swaps. A line that does not start with the
    source marker is returned unchanged.
    """
    if not line.startswith(source):
        return line
    if len(line) >= 2 * len(source) and line.endswith(source):
        inner = line[len(source) : -len(source)]
        return f"{target}{inner}{target}"
    return target + line[len(source) :]


def render_variant(banner: CanonicalBanner, variant: str) -> list[str]:
    """Render the canonical SPDX header line in the requested variant.

    Args:
        banner: Parsed canonical header (the single SPDX line).
        variant: One of the ``VARIANT_*`` constants other than
            ``VARIANT_EXEMPT``.

    Returns:
        A single-line list. The hash variant emits the byte-exact fixture
        line (``# SPDX-License-Identifier: MIT``); double-slash, semicolon,
        and double-dash variants substitute the leading marker via
        ``_replace_marker``; html wraps the SPDX text in ``<!-- ... -->``;
        c-block wraps it in ``/* ... */``.

    Raises:
        ValueError: When ``variant`` is unknown or is ``VARIANT_EXEMPT``.
    """
    if variant == VARIANT_HASH:
        return [banner.hash_form_line]
    if variant == VARIANT_DOUBLE_SLASH:
        return [_replace_marker(banner.hash_form_line, "#", "//")]
    if variant == VARIANT_SEMICOLON:
        return [_replace_marker(banner.hash_form_line, "#", ";")]
    if variant == VARIANT_DOUBLE_DASH:
        return [_replace_marker(banner.hash_form_line, "#", "--")]
    if variant == VARIANT_HTML:
        return [f"<!-- {banner.spdx_text} -->"]
    if variant == VARIANT_C_BLOCK:
        return [f"/* {banner.spdx_text} */"]
    raise ValueError(f"variant not renderable: {variant}")


# ---------------------------------------------------------------------------
# Variant resolution.
# ---------------------------------------------------------------------------


def variant_family_for(relative_path: Path) -> str:
    """Resolve the canonical variant family for the file's filetype.

    Suffix lookup is the primary signal; basename overrides cover
    suffix-less artifacts (Makefile, Dockerfile, dotfiles whose name
    encodes the convention). When neither resolves, the file is treated
    as ``exempt``; the exception fixture remains the authoritative
    applicability gate.

    Args:
        relative_path: A path relative to the repository root.

    Returns:
        One of the ``VARIANT_*`` string constants.
    """
    name = relative_path.name
    if name in BASENAME_VARIANT:
        return BASENAME_VARIANT[name]
    suffix = relative_path.suffix.lower()
    if suffix in SUFFIX_VARIANT:
        return SUFFIX_VARIANT[suffix]
    return VARIANT_EXEMPT


# ---------------------------------------------------------------------------
# Exception fixture parsing.
# ---------------------------------------------------------------------------


def load_exception_globs(fixture_path: Path) -> list[str]:
    """Parse the header-exceptions glob fixture into an ordered glob list.

    Comment lines (``#``-prefixed) and blank lines are stripped. The
    declaration order is preserved so a future deny-list / allow-list
    extension can rely on first-match semantics.

    Args:
        fixture_path: Path to ``src/apothem/schemas/header-exceptions.txt``.

    Returns:
        Glob patterns in declaration order. An empty list when the file
        is missing (the absent fixture is treated as empty rather than
        as an error so a tmpdir-rooted invocation without an exceptions
        file behaves gracefully).
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
    """Return the first matching glob, or ``None`` when the path is in scope."""
    posix = relative_path.replace("\\", "/")
    for pattern in globs:
        if _fnmatch_with_globstar(posix, pattern):
            return pattern
    return None


def _fnmatch_with_globstar(path: str, pattern: str) -> bool:
    """fnmatch with ``**`` cross-segment expansion (gitignore semantics).

    fnmatch alone treats ``*`` as non-greedy across separators; ``**``
    here matches zero or more path segments. Translation is direct —
    character-by-character regex synthesis with the four glob-significant
    tokens (``**``, ``*``, ``?``, character classes) handled inline;
    ordinary characters are escaped via ``re.escape``.
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
                if i + 2 < pattern_length and pattern[i + 2] == "/":
                    regex_parts.append("(?:.*/)?")
                    i += 3
                    continue
                regex_parts.append(".*")
                i += 2
                continue
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


# ---------------------------------------------------------------------------
# Per-file injection.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FileVerdict:
    """Per-file outcome of an injector pass.

    Attributes:
        relative_path: POSIX-style path relative to the repository root.
        applicable: True when the file is in scope for the banner.
        variant: The resolved variant family.
        action: One of ``"noop"`` (canonical present),
            ``"would-write"`` (mode ``check``/``emit-patch`` with
            divergence), ``"wrote"`` (mode ``fix-in-place`` applied a
            change), ``"skipped"`` (exempt).
        diff: Unified diff text for divergence; empty for ``noop``
            and ``skipped``.
    """

    relative_path: str
    applicable: bool
    variant: str
    action: str
    diff: str


def has_shebang(content: str) -> bool:
    """Return True when ``content`` begins with a ``#!`` shebang."""
    return content.startswith("#!")


def _frontmatter_close_index(lines: list[str], start_index: int) -> int | None:
    """Return the closing line index for YAML frontmatter, if present."""
    if start_index >= len(lines) or lines[start_index] != "---":
        return None
    for index in range(start_index + 1, len(lines)):
        if lines[index] == "---":
            return index
    return None


def determine_insertion_index(lines: list[str], variant: str) -> int:
    """Return the zero-based line index at which the banner is inserted.

    The banner is the first file content except for a shebang and, for
    Markdown/MDX HTML-comment banners, YAML frontmatter. Frontmatter must
    remain byte-first so static-site and documentation generators can parse
    collection metadata before reading the Markdown body.
    """
    insertion_index = 1 if lines and lines[0].startswith("#!") else 0
    if variant == VARIANT_HTML:
        frontmatter_end = _frontmatter_close_index(lines, insertion_index)
        if frontmatter_end is not None:
            insertion_index = frontmatter_end + 1
            if insertion_index < len(lines) and lines[insertion_index].strip() == "":
                insertion_index += 1
    return insertion_index


def render_canonical_block(banner: CanonicalBanner, variant: str) -> list[str]:
    """Render the canonical banner with a trailing blank-line separator.

    Per spec §4.6.3 the banner is followed by exactly one blank line so
    the next content reads as a separate region. Markdown/MDX frontmatter
    remains ahead of the banner; this block separates the banner from the
    rendered body content. The trailing blank is part of the canonical block
    to keep idempotency a byte-exact comparison.
    """
    return [*render_variant(banner, variant), ""]


def is_canonical_at_position(
    content_lines: list[str],
    canonical_block: list[str],
    insertion_index: int,
) -> bool:
    """Return True when ``canonical_block`` already sits at ``insertion_index``."""
    end = insertion_index + len(canonical_block)
    if end > len(content_lines):
        return False
    return content_lines[insertion_index:end] == canonical_block


def _split_lines_preserving(content: str) -> list[str]:
    """Split content into lines without trailing newlines, preserving counts.

    A trailing newline at end-of-file produces an empty element, which
    matches the Unix-text invariant where well-formed text files end in
    a newline. Round-tripping through ``"\\n".join(lines)`` reproduces
    the original byte-exact when the source ended in a newline.
    """
    return content.split("\n")


def _join_lines_preserving(lines: list[str]) -> str:
    """Inverse of :func:`_split_lines_preserving`: rejoin with ``\\n``."""
    return "\n".join(lines)


def _strip_existing_banner(
    lines: list[str],
    insertion_index: int,
    variant: str,
) -> list[str]:
    """Remove any pre-existing banner-shaped block at ``insertion_index``.

    A canonical-but-mis-positioned banner, or a malformed banner whose
    Copyright author-line lies within the scan budget, is stripped before
    re-injection so the result is idempotent under repeated runs. When
    no author mark is found, the original lines are returned unchanged.

    The detection signal is the literal ``AUTHOR_MARK`` substring on a
    line within the scan budget. Once found, the helper inspects the
    line immediately above the author line for ``SPDX_PREFIX_TEXT`` to
    distinguish the new 6-line form (SPDX top + 5 contact lines, with
    the author line at row 2 of the banner) from the legacy 5-line form
    (no SPDX line, with the author line at row 1 of the banner). The
    contiguous block sized accordingly (plus any immediately following
    blank line) is removed. This logic is required because the codebase
    may carry both shapes during the D9 migration window: legacy headers
    are removed and replaced with the new form on first injection, and
    subsequent runs are no-ops against the new form.
    """
    scan_end = min(len(lines), insertion_index + SCAN_LINE_BUDGET)
    author_line_index: int | None = None
    for index in range(insertion_index, scan_end):
        if AUTHOR_MARK in lines[index]:
            author_line_index = index
            break
    if author_line_index is None:
        return lines

    # Detect whether the banner above carries the SPDX top line (new form)
    # or omits it (legacy form). The SPDX line sits one row above the
    # author line in the new form (line variants) or two rows above in
    # wrapper variants (the wrapper's opener intervenes).
    new_form_line_variant = (
        variant not in (VARIANT_HTML, VARIANT_C_BLOCK)
        and author_line_index > insertion_index
        and SPDX_PREFIX_TEXT in lines[author_line_index - 1]
    )
    new_form_wrapper_variant = (
        variant in (VARIANT_HTML, VARIANT_C_BLOCK)
        and author_line_index > insertion_index + 1
        and SPDX_PREFIX_TEXT in lines[author_line_index - 1]
    )

    if variant in (VARIANT_HTML, VARIANT_C_BLOCK):
        if new_form_wrapper_variant:
            # Eight lines: wrapper-open + SPDX + 5 contact + wrapper-close.
            # author_line is row 3 of the eight (wrapper-open at row 1,
            # SPDX at row 2, Copyright at row 3).
            block_start = max(insertion_index, author_line_index - 2)
            expected_count = 8
        else:
            # Legacy seven-line form: wrapper-open + 5 contact + wrapper-close.
            # author_line is row 2 (wrapper-open at row 1, Copyright at row 2).
            block_start = max(insertion_index, author_line_index - 1)
            expected_count = 7
    elif new_form_line_variant:
        # New 6-line form: SPDX + 5 contact lines. author_line is row 2.
        block_start = author_line_index - 1
        expected_count = 6
    else:
        # Legacy 5-line form: 5 contact lines. author_line is row 1.
        block_start = author_line_index
        expected_count = 5

    block_end_exclusive = min(len(lines), block_start + expected_count)
    if block_end_exclusive < len(lines) and lines[block_end_exclusive].strip() == "":
        block_end_exclusive += 1
    return lines[:block_start] + lines[block_end_exclusive:]


def inject_banner(
    content: str,
    banner: CanonicalBanner,
    variant: str,
) -> tuple[str, bool]:
    """Insert the canonical banner at the correct position.

    Args:
        content: Original file content.
        banner: Parsed canonical banner.
        variant: Variant family for this file.

    Returns:
        ``(new_content, changed)``. ``changed`` is False when the
        banner was already canonical at the insertion site (idempotency).
    """
    canonical_block = render_canonical_block(banner, variant)
    lines = _split_lines_preserving(content)
    insertion_index = determine_insertion_index(lines, variant)
    trimmed = _strip_existing_banner(lines, insertion_index, variant)
    if trimmed == lines and insertion_index != 0:
        trimmed = _strip_existing_banner(lines, 0, variant)

    insertion_index = determine_insertion_index(trimmed, variant)
    if is_canonical_at_position(trimmed, canonical_block, insertion_index):
        return content, False

    new_lines = trimmed[:insertion_index] + canonical_block + trimmed[insertion_index:]
    new_content = _join_lines_preserving(new_lines)
    return new_content, new_content != content


def make_unified_diff(
    relative_path: str,
    before: str,
    after: str,
) -> str:
    """Return a standard unified diff between ``before`` and ``after``."""
    if before == after:
        return ""
    diff_lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
        lineterm="",
    )
    return "".join(diff_lines)


def process_file(
    absolute_path: Path,
    relative_path: str,
    banner: CanonicalBanner,
    exceptions: list[str],
    mode: str,
) -> FileVerdict:
    """Process a single file under the requested mode.

    Args:
        absolute_path: Real on-disk path to the file.
        relative_path: POSIX-style path relative to the root.
        banner: Parsed canonical banner.
        exceptions: Loaded exception globs.
        mode: One of ``MODE_FIX`` / ``MODE_PATCH`` / ``MODE_CHECK``.

    Returns:
        A ``FileVerdict`` capturing applicability, variant, action, diff.
    """
    if matches_exception(relative_path, exceptions) is not None:
        return FileVerdict(
            relative_path=relative_path,
            applicable=False,
            variant=VARIANT_EXEMPT,
            action="skipped",
            diff="",
        )

    variant = variant_family_for(Path(relative_path))
    if variant == VARIANT_EXEMPT:
        return FileVerdict(
            relative_path=relative_path,
            applicable=False,
            variant=VARIANT_EXEMPT,
            action="skipped",
            diff="",
        )

    try:
        original = absolute_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return FileVerdict(
            relative_path=relative_path,
            applicable=False,
            variant=variant,
            action="skipped",
            diff="",
        )

    new_content, changed = inject_banner(original, banner, variant)
    if not changed:
        return FileVerdict(
            relative_path=relative_path,
            applicable=True,
            variant=variant,
            action="noop",
            diff="",
        )

    diff = make_unified_diff(relative_path, original, new_content)

    if mode == MODE_FIX:
        absolute_path.write_text(new_content, encoding="utf-8")
        return FileVerdict(
            relative_path=relative_path,
            applicable=True,
            variant=variant,
            action="wrote",
            diff=diff,
        )
    return FileVerdict(
        relative_path=relative_path,
        applicable=True,
        variant=variant,
        action="would-write",
        diff=diff,
    )


# ---------------------------------------------------------------------------
# Path expansion & CLI.
# ---------------------------------------------------------------------------


def _record(
    absolute_path: Path,
    root: Path,
    pairs: list[tuple[Path, str]],
    seen: set[Path],
) -> None:
    """Append a unique ``(absolute, relative)`` pair to ``pairs``."""
    resolved = absolute_path.resolve()
    if resolved in seen:
        return
    seen.add(resolved)
    try:
        relative_path = resolved.relative_to(root.resolve())
        relative_str = str(relative_path).replace("\\", "/")
    except ValueError:
        relative_str = str(absolute_path).replace("\\", "/")
    pairs.append((absolute_path, relative_str))


def expand_paths(root: Path, paths: list[str]) -> list[tuple[Path, str]]:
    """Expand the input paths into a list of ``(absolute, relative)`` pairs.

    Each input may be a literal file path, a directory (walked
    recursively), or a glob (resolved against ``root``). Results are
    deduplicated by resolved absolute path; order follows the input
    order with a deterministic per-input filesystem walk.

    Args:
        root: Repository root the relative paths are anchored to.
        paths: User-supplied path arguments.

    Returns:
        A list of ``(absolute_path, relative_str)`` pairs.
    """
    pairs: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for raw in paths:
        candidate = (root / raw) if not Path(raw).is_absolute() else Path(raw)
        if candidate.is_file():
            _record(candidate, root, pairs, seen)
            continue
        if candidate.is_dir():
            for child in sorted(candidate.rglob("*")):
                if child.is_file():
                    _record(child, root, pairs, seen)
            continue
        for match in sorted(root.glob(raw)):
            if match.is_file():
                _record(match, root, pairs, seen)
            elif match.is_dir():
                for child in sorted(match.rglob("*")):
                    if child.is_file():
                        _record(child, root, pairs, seen)
    return pairs


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the CLI arguments into an ``argparse.Namespace``."""
    parser = argparse.ArgumentParser(
        prog="inject-header.py",
        description=(
            "Deterministic authorship-header injector. Reads "
            "src/apothem/schemas/authorship-header.txt for the canonical banner; "
            "src/apothem/schemas/header-exceptions.txt for applicability; emits the "
            "correct per-filetype variant at the correct insertion "
            "position. Idempotent under repeated runs."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=ALL_MODES,
        default=MODE_FIX,
        help="Operation mode (default: fix-in-place).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current working directory).",
    )
    parser.add_argument(
        "--banner",
        type=Path,
        default=None,
        help=f"Banner fixture (default: <root>/{DEFAULT_BANNER_PATH}).",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=None,
        help=f"Exception fixture (default: <root>/{DEFAULT_EXCEPTIONS_PATH}).",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files, directories, or globs to process.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Args:
        argv: Optional argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        ``EXIT_OK`` on success or no divergence; ``EXIT_DIVERGENCE`` when
        ``check`` mode finds divergence; ``EXIT_ERROR`` on irrecoverable
        error (missing fixture, invalid argument).
    """
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = args.root.resolve()
    banner_path = args.banner if args.banner is not None else root / DEFAULT_BANNER_PATH
    exceptions_path = (
        args.exceptions
        if args.exceptions is not None
        else root / DEFAULT_EXCEPTIONS_PATH
    )

    try:
        banner = load_canonical_banner(banner_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    exceptions = load_exception_globs(exceptions_path)

    pairs = expand_paths(root, args.paths)
    if not pairs:
        print("warning: no files matched the input paths", file=sys.stderr)
        return EXIT_OK

    divergence_found = False
    for absolute_path, relative_path in pairs:
        verdict = process_file(
            absolute_path,
            relative_path,
            banner,
            exceptions,
            args.mode,
        )
        if verdict.action == "would-write":
            divergence_found = True
            if args.mode == MODE_PATCH:
                sys.stdout.write(verdict.diff)
            else:
                print(
                    f"divergence: {verdict.relative_path} (variant: {verdict.variant})",
                    file=sys.stderr,
                )
        elif verdict.action == "wrote":
            print(f"wrote: {verdict.relative_path}")

    if args.mode == MODE_CHECK and divergence_found:
        return EXIT_DIVERGENCE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
