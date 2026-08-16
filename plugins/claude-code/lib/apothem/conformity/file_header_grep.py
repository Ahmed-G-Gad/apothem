# SPDX-License-Identifier: MIT

"""file-header-grep: authorship-header presence and canonical-form check.

Why self-contained. Grep modules under conformity/ are hot-loaded via
importlib; cross-directory imports from scripts/ are unavailable at that
execution surface. All helpers are inlined from scripts/inject-header.py with
byte-identical semantics so the validator and the injector share algorithmic
parity without sharing a Python module.

Verdict matrix:
    pass    — header canonical at insertion site, file is exempt, or
              variant is unknown (no applicable check).
    ABSENT  — no AUTHOR_MARK found within the first SCAN_LINE_BUDGET lines;
              the header is entirely missing.
    MALFORMED — a header marker is present but the block is not canonical:
              either the legacy AUTHOR_MARK appears within SCAN_LINE_BUDGET,
              or an SPDX line sits at the insertion site in a non-canonical
              form (wrong comment family, wrong license, or a missing
              mandatory trailing blank).
"""

from __future__ import annotations

import functools
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------

GREP_NAME: Final[str] = "file-header-grep"

# ---------------------------------------------------------------------------
# Detection constants (mirrors inject-header.py)
# ---------------------------------------------------------------------------

AUTHOR_MARK: Final[str] = "Copyright (c) Ahmed G. Gad"
SCAN_LINE_BUDGET: Final[int] = 60

# Marker substring that identifies the SPDX license-identifier line.
# Mirrors scripts/inject-header.py SPDX_PREFIX_TEXT so the matcher and
# the injector share canonical-form detection without sharing a module.
SPDX_PREFIX_TEXT: Final[str] = "SPDX-License-Identifier:"

# ---------------------------------------------------------------------------
# Variant-family constants
# ---------------------------------------------------------------------------

VARIANT_HASH: Final[str] = "hash"
VARIANT_DOUBLE_SLASH: Final[str] = "double-slash"
VARIANT_HTML: Final[str] = "html"
VARIANT_C_BLOCK: Final[str] = "c-block"
VARIANT_SEMICOLON: Final[str] = "semicolon"
VARIANT_DOUBLE_DASH: Final[str] = "double-dash"
VARIANT_EXEMPT: Final[str] = "exempt"

# Suffix → variant (mirrors inject-header.py SUFFIX_VARIANT)
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
    ".xml": VARIANT_HTML,
    ".svg": VARIANT_HTML,
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

# Basename → variant for suffix-less files (mirrors inject-header.py BASENAME_VARIANT)
BASENAME_VARIANT: Final[dict[str, str]] = {
    "Makefile": VARIANT_HASH,
    "Dockerfile": VARIANT_HASH,
    "Procfile": VARIANT_HASH,
    ".gitignore": VARIANT_HASH,
    ".gitattributes": VARIANT_HASH,
    ".editorconfig": VARIANT_HASH,
    ".shellcheckrc": VARIANT_HASH,
    ".env.example": VARIANT_HASH,
    ".cursorrules": VARIANT_HASH,
    ".windsurfrules": VARIANT_HASH,
}

# ---------------------------------------------------------------------------
# Filesystem anchors
# ---------------------------------------------------------------------------

# Dual-shape anchors. The conformity package ships beside its ``schemas/``
# sibling in both supported layouts — the repo checkout
# (``src/apothem/{conformity,schemas}``) and the installed tree
# (``<install-root>/apothem/{conformity,schemas}``) — so the schema and
# fixture files always sit one parent hop above this module.
SCHEMAS_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "schemas"

# Working-tree root anchor. In the repo checkout, parents[3] of
# ``src/apothem/conformity/<file>.py`` is the working-tree root, so paths
# computed via relative_to(ECOSYSTEM_ROOT) align with the
# working-tree-rooted globs in header-exceptions.txt (LICENSE, .apothem/**,
# tests/fixtures/**, ...). In the installed tree the anchor is a coarse
# filesystem ancestor: dispatched paths beneath it still resolve (the
# header check stays active; the repo-rooted globs simply do not match),
# and paths outside it degrade to a pass-through via the relative_to()
# guard in check().
ECOSYSTEM_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Rule identifiers
# ---------------------------------------------------------------------------

RULE_ABSENT: Final[str] = "HEADER_ABSENT"
RULE_MALFORMED: Final[str] = "HEADER_MALFORMED"

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One diagnostic finding emitted when a header check fails."""

    line: int
    match: str
    context: str
    rule: str


# ---------------------------------------------------------------------------
# Inlined helpers — algorithmic parity with scripts/inject-header.py
# ---------------------------------------------------------------------------


def _fnmatch_with_globstar(path: str, pattern: str) -> bool:
    """fnmatch with ``**`` cross-segment expansion (gitignore semantics).

    Ordinary ``*`` matches within a single path segment; ``**`` matches
    zero or more full segments including directory separators.
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
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                if i + 2 < n and pattern[i + 2] == "/":
                    regex_parts.append("(?:.*/)?")
                    i += 3
                    continue
                regex_parts.append(".*")
                i += 2
                continue
            regex_parts.append("[^/]*")
            i += 1
            continue
        if ch == "?":
            regex_parts.append("[^/]")
            i += 1
            continue
        regex_parts.append(re.escape(ch))
        i += 1
    full = "^" + "".join(regex_parts) + "$"
    return re.match(full, path) is not None


def _replace_marker(line: str, source: str, target: str) -> str:
    """Substitute the comment marker on a banner line.

    Banner lines come in two shapes: bordered (rows 2-6 of the canonical
    fixture; marker on both edges) and prefix-only (row 1, the SPDX line;
    marker on the leading edge only). Bordered lines swap both edges;
    prefix-only lines swap the leading edge. Mirrors the logic at
    scripts/inject-header.py to preserve injector / matcher parity.
    """
    if not line.startswith(source):
        return line
    if len(line) >= 2 * len(source) and line.endswith(source):
        inner = line[len(source) : -len(source)]
        return f"{target}{inner}{target}"
    return target + line[len(source) :]


def _render_variant(
    hash_form_line: str,
    spdx_text: str,
    variant: str,
) -> list[str]:
    """Render the canonical SPDX header line for *variant* (no trailing blank)."""
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
    hash_form_line: str,
    spdx_text: str,
    variant: str,
) -> list[str]:
    """Render the canonical block including the mandatory trailing blank line."""
    return [*_render_variant(hash_form_line, spdx_text, variant), ""]


@functools.cache
def _load_banner() -> tuple[str, str]:
    """Load the canonical SPDX-line header fixture (memoized per process).

    The NARROW header (D-007) is the single machine-readable
    ``# SPDX-License-Identifier: MIT`` line; the retired branded banner
    box no longer participates. Mirrors scripts/inject-header.py
    load_canonical_banner.

    Memoized because ``check()`` calls it on every invocation and the fixture
    is immutable per process; under the corpus per-Write run (one ``check``
    per tracked file) the un-cached read re-hit disk once per file. The result
    tuple is immutable, so the shared cache entry is safe.

    Returns:
        ``(hash_form_line, spdx_text)`` on success; two empty strings
        when the fixture is absent or malformed (the caller treats the
        empty result as a pass-through skip).
    """
    banner_path = SCHEMAS_DIR / "authorship-header.txt"
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


@functools.cache
def _load_exception_globs() -> tuple[str, ...]:
    """Parse the header-exceptions fixture into an ordered glob tuple.

    Memoized per process: ``check()`` reads it on every invocation and the
    fixture is immutable, so the corpus per-Write run no longer re-parses it
    once per tracked file. The return is a tuple (immutable) so the shared
    cache entry cannot be mutated by a caller.
    """
    fixture_path = SCHEMAS_DIR / "header-exceptions.txt"
    if not fixture_path.is_file():
        return ()
    globs: list[str] = []
    for raw_line in fixture_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        globs.append(stripped)
    return tuple(globs)


def _matches_exception(relative_path: str, globs: tuple[str, ...]) -> bool:
    """Return True when *relative_path* matches any exception glob."""
    posix = relative_path.replace("\\", "/")
    return any(_fnmatch_with_globstar(posix, pattern) for pattern in globs)


def _variant_family_for(relative_path: Path) -> str:
    """Resolve the canonical variant family for a file.

    Basename lookup takes precedence over suffix lookup; unknown files
    return VARIANT_EXEMPT (no applicable header variant).
    """
    name = relative_path.name
    if name in BASENAME_VARIANT:
        return BASENAME_VARIANT[name]
    suffix = relative_path.suffix.lower()
    return SUFFIX_VARIANT.get(suffix, VARIANT_EXEMPT)


def _is_canonical_at_position(
    content_lines: list[str],
    canonical_block: list[str],
    insertion_index: int,
) -> bool:
    """Return True when *canonical_block* sits byte-exact at *insertion_index*."""
    end = insertion_index + len(canonical_block)
    if end > len(content_lines):
        return False
    return content_lines[insertion_index:end] == canonical_block


def _determine_insertion_index(content: str) -> int:
    """Return the zero-based line index for banner insertion.

    A shebang (``#!``) on the first line pushes the banner to line index 1.
    """
    return 1 if content.startswith("#!") else 0


# ---------------------------------------------------------------------------
# Public check entry point
# ---------------------------------------------------------------------------


def _relative_to_anchor(abs_path: Path) -> Path | None:
    """Return *abs_path* relative to the repo root or its matched hook scope.

    The apothem repo root (``ECOSYSTEM_ROOT``) is tried first, so the gate run
    over the repo behaves exactly as before. When the path is outside the repo,
    the configured conformity scopes (the hook-capable harness roots, via
    ``gate.scope_relative_path``) are tried, so a per-Write hook target such as
    ``~/.claude/rules/x.md`` is evaluated relative to ``~/.claude`` instead of
    silently passing. Returns ``None`` when *abs_path* is under no anchor (a true
    pass-through — there is no scope to resolve exception globs / variant family
    against).
    """
    try:
        return abs_path.relative_to(ECOSYSTEM_ROOT)
    except ValueError:
        pass
    # Lazy import: the gate module hot-loads this matcher at runtime, so importing
    # it at call time (not module top) keeps the two free of any import coupling.
    from apothem.conformity.gate import scope_relative_path

    scoped = scope_relative_path(abs_path)
    return scoped[1] if scoped is not None else None


def check(content: str, path: Path | None = None) -> GrepResult:
    """Validate authorship-header presence and canonical form for *path*.

    Args:
        content: Full text of the file being checked.
        path: Absolute path to the file; when ``None`` the check is
            skipped (cannot determine exception applicability).

    Returns:
        A ``GrepResult`` with ``passed=True`` when the header is canonical,
        the file is exempt, or the file's variant is unknown. ``passed=False``
        with a ``Finding`` of rule ``HEADER_ABSENT`` or ``HEADER_MALFORMED``
        otherwise.
    """
    if path is None:
        return GrepResult(grep=GREP_NAME, path=None, passed=True)

    abs_path = path.resolve()
    rel_path = _relative_to_anchor(abs_path)
    if rel_path is None:
        # Outside the apothem repo root AND every configured hook scope — there
        # is no anchor to resolve exception globs / variant family against; skip.
        return GrepResult(grep=GREP_NAME, path=str(path), passed=True)

    rel_str = str(rel_path)

    exception_globs = _load_exception_globs()
    if _matches_exception(rel_str, exception_globs):
        return GrepResult(grep=GREP_NAME, path=str(path), passed=True)

    variant = _variant_family_for(rel_path)
    if variant == VARIANT_EXEMPT:
        return GrepResult(grep=GREP_NAME, path=str(path), passed=True)

    hash_form_line, spdx_text = _load_banner()
    if not hash_form_line:
        # Banner fixture missing or malformed — cannot validate; skip.
        return GrepResult(grep=GREP_NAME, path=str(path), passed=True)

    canonical_block = _render_canonical_block(hash_form_line, spdx_text, variant)
    content_lines = content.split("\n")
    insertion_index = _determine_insertion_index(content)

    if _is_canonical_at_position(content_lines, canonical_block, insertion_index):
        return GrepResult(grep=GREP_NAME, path=str(path), passed=True)

    # Not canonical. Classify the failure as MALFORMED (a header is present but
    # wrong) or ABSENT (no header marker at all). Two MALFORMED shapes:
    #   (a) the retired branded-box form — the legacy AUTHOR_MARK appears
    #       anywhere within the scan window;
    #   (b) a present-but-non-canonical SPDX line at the insertion site —
    #       wrong comment family (e.g. ``//`` in a hash-variant file), wrong
    #       license, or a missing mandatory trailing blank. The marker is
    #       present at the header position but the block is not canonical, so
    #       the header is malformed, not absent.
    scan_end = min(len(content_lines), insertion_index + SCAN_LINE_BUDGET)
    for idx in range(insertion_index, scan_end):
        if AUTHOR_MARK in content_lines[idx]:
            return GrepResult(
                grep=GREP_NAME,
                path=str(path),
                passed=False,
                findings=[
                    Finding(
                        line=idx + 1,
                        match=content_lines[idx],
                        context=(
                            f"authorship header found but not in canonical form"
                            f" for variant '{variant}'"
                        ),
                        rule=RULE_MALFORMED,
                    )
                ],
            )

    if (
        insertion_index < len(content_lines)
        and SPDX_PREFIX_TEXT in content_lines[insertion_index]
    ):
        return GrepResult(
            grep=GREP_NAME,
            path=str(path),
            passed=False,
            findings=[
                Finding(
                    line=insertion_index + 1,
                    match=content_lines[insertion_index],
                    context=(
                        f"SPDX header present at the insertion site but not in"
                        f" canonical form for variant '{variant}'"
                    ),
                    rule=RULE_MALFORMED,
                )
            ],
        )

    # No header marker anywhere in the scan window — header is absent.
    return GrepResult(
        grep=GREP_NAME,
        path=str(path),
        passed=False,
        findings=[
            Finding(
                line=insertion_index + 1,
                match="",
                context=(
                    f"authorship header absent; expected variant '{variant}'"
                    f" at line {insertion_index + 1}"
                ),
                rule=RULE_ABSENT,
            )
        ],
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
