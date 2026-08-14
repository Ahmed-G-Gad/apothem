# SPDX-License-Identifier: MIT

"""Why this module exists — reading a file head and judging what it carries.

This is the stage that actually touches file bytes. Everything upstream is
path arithmetic: which comment family, is the file in scope, what would
canonical look like. Here a real head is read and compared, and the comparison
has to distinguish "no header" from "a header, but wrong" from "the right
header, malformed" — three outcomes that drive three different remediations.

Scope. Bounded head reading, shebang and insertion-point arithmetic, the
banner scan that classifies status and malformation class, and the injection
plan that renders a unified diff the downstream injector can apply. Nothing
here writes: the plan is a preview, and applying it belongs to the injector.

Detection strategy. Only the first ``SCAN_LINE_BUDGET`` lines are read, which
absorbs every shebang plus frontmatter plus banner shape the canonical
variants emit while keeping one oversized file from stalling a whole-tree
scan. A wrong-variant check runs before the malformation checks, because a
hash-family line in a Markdown file is a variant error rather than eight
separate malformation findings.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from apothem.audit.header_banner import canonical_banner_lines, canonical_block_lines
from apothem.audit.header_vocabulary import (
    BOM_PREFIX,
    DIFF_CONTEXT_LINES,
    HEADER_ABSENT,
    HEADER_NOT_APPLICABLE,
    HEADER_PRESENT_CANONICAL,
    HEADER_PRESENT_MALFORMED,
    LEGACY_AUTHOR_MARK,
    MALFORM_BOM_PREFIX,
    MALFORM_MIXED,
    MALFORM_SMART_QUOTE,
    MALFORM_TRAILING_WHITESPACE,
    MALFORM_WRONG_LINE_COUNT,
    MALFORM_WRONG_VARIANT,
    SCAN_LINE_BUDGET,
    SMART_QUOTES,
    SPDX_PREFIX_TEXT,
    VARIANT_C_BLOCK,
    VARIANT_DOUBLE_DASH,
    VARIANT_DOUBLE_SLASH,
    VARIANT_EXEMPT,
    VARIANT_HASH,
    VARIANT_HTML,
    VARIANT_SEMICOLON,
)


def read_head(absolute_path: Path, line_budget: int = SCAN_LINE_BUDGET) -> list[str]:
    """Return the file's leading lines (without trailing newlines).

    UTF-8 with replacement fallback keeps mixed-encoding corpora
    walkable. A binary file mis-classified as text yields garbled lines
    but never crashes the scan.
    """
    try:
        with absolute_path.open("r", encoding="utf-8", errors="replace") as handle:
            head: list[str] = []
            for index, line in enumerate(handle):
                if index >= line_budget:
                    break
                head.append(line.rstrip("\r\n"))
            return head
    except OSError:
        return []


def has_shebang(head_lines: list[str]) -> bool:
    """Return ``True`` when the first line begins with ``#!``."""
    return bool(head_lines) and head_lines[0].startswith("#!")


def insertion_line(head_lines: list[str]) -> int:
    """Return the 1-based line at which the canonical banner is inserted.

    The banner is the file's first content with the single exception of
    a shebang line (``#!``), which always remains line 1; the banner
    starts on line 2 in that case. Frontmatter (``---``) follows the
    banner per spec §4.6.3.
    """
    return 2 if has_shebang(head_lines) else 1


def scan_for_banner(
    head_lines: list[str], variant: str
) -> tuple[str, tuple[int, int] | None, str | None, str | None]:
    """Inspect leading lines for the canonical header and return a verdict.

    Returns a 4-tuple ``(header_status, line_range, malformation_class,
    malformation_detail)``. ``line_range`` is ``None`` for absent headers;
    the others carry detail when the header is present but malformed.

    The narrowed header is a single line, so the verdict reduces to a
    byte-exact comparison of the canonical block (the SPDX line plus its
    mandatory trailing blank) at the insertion site — the same block the
    validator at file_header_grep.py compares. A header present at the site
    but not byte-exact is classified against the malformation slots a
    one-line header can exhibit: bom-prefix, smart-quote-pollution,
    trailing-whitespace, wrong-variant, and a wrong-line-count fall-through.
    The retired branded-banner box (whose first line was the SPDX line but
    which lacks the trailing blank) lands here as not-yet-narrowed; a file
    with neither the SPDX line nor the legacy author mark is absent.
    """
    if not head_lines:
        return HEADER_ABSENT, None, None, None

    # BOM detection is independent of variant: any BOM byte before the
    # header is itself a malformation, even if the rest is byte-exact.
    bom_observed = head_lines[0].startswith(BOM_PREFIX)

    # Canonical block = the variant line plus one trailing blank, mirroring
    # _render_canonical_block / file_header_grep's _is_canonical_at_position.
    canonical_block = canonical_block_lines(variant)

    # The header sits at the insertion site: line index 1 after a shebang,
    # else line index 0. The reported range is the SPDX line itself (the
    # trailing blank completes the block but is not part of the header).
    site_index = 1 if has_shebang(head_lines) else 0
    if site_index >= len(head_lines):
        # The file is shorter than the insertion site — header absent.
        return HEADER_ABSENT, None, None, None

    observed_line = head_lines[site_index]
    line_range = (site_index + 1, site_index + 1)

    # Byte-exact comparison of the full canonical block at the site.
    block_end = site_index + len(canonical_block)
    block_canonical = (
        block_end <= len(head_lines)
        and head_lines[site_index:block_end] == canonical_block
    )
    if block_canonical and not bom_observed:
        return HEADER_PRESENT_CANONICAL, line_range, None, None

    # The site does not carry the byte-exact canonical line. Decide whether
    # any recognizable header is present at all: a SPDX line in some shape,
    # or the retired branded-banner author mark anywhere in the head.
    spdx_at_site = SPDX_PREFIX_TEXT in observed_line
    legacy_present = any(LEGACY_AUTHOR_MARK in line for line in head_lines)

    if not spdx_at_site and not legacy_present and not bom_observed:
        return HEADER_ABSENT, None, None, None

    # A recognizable-but-non-canonical header is present. Classify the
    # malformation against the slots a one-line header can exhibit; multiple
    # matches collapse to ``mixed``.
    detected: list[tuple[str, str]] = []

    if bom_observed:
        detected.append((MALFORM_BOM_PREFIX, "U+FEFF byte order mark prefix"))

    # Smart-quote pollution: any non-ASCII smart quote on the header line.
    smart_hits = [q for q in SMART_QUOTES if q in observed_line]
    if smart_hits:
        detected.append(
            (
                MALFORM_SMART_QUOTE,
                "non-ASCII typography in header: "
                + ", ".join(repr(q) for q in smart_hits),
            )
        )

    # Trailing whitespace: the header line carries whitespace beyond the
    # canonical line's content.
    if observed_line.rstrip() != observed_line:
        detected.append(
            (MALFORM_TRAILING_WHITESPACE, "trailing whitespace on header line"),
        )

    # Wrong-variant: the SPDX line uses a comment marker different from the
    # canonical for this filetype.
    if spdx_at_site:
        wrong_variant = _detect_wrong_variant(observed_line, variant)
        if wrong_variant is not None:
            detected.append(
                (MALFORM_WRONG_VARIANT, f"header uses {wrong_variant!r} marker"),
            )

    # Fall-through: present but not byte-exact and no finer class fired.
    # The retired branded-banner box is a not-yet-narrowed header and lands
    # here as a wrong-line-count (the multi-line legacy box vs. one line).
    if not detected:
        if legacy_present and not spdx_at_site:
            detected.append(
                (
                    MALFORM_WRONG_LINE_COUNT,
                    "retired branded-banner box present; expected single SPDX line",
                ),
            )
        else:
            detected.append(
                (
                    MALFORM_WRONG_LINE_COUNT,
                    "header present but does not match canonical bytes",
                ),
            )

    # Resolve to a single class: more than one finding ⇒ mixed.
    if len(detected) == 1:
        cls, detail = detected[0]
    else:
        cls = MALFORM_MIXED
        detail = "; ".join(f"{c}: {d}" for c, d in detected)

    return HEADER_PRESENT_MALFORMED, line_range, cls, detail


def _detect_wrong_variant(observed_line: str, target_variant: str) -> str | None:
    """Return the comment-syntax marker observed on the SPDX header line when
    it disagrees with the target variant; ``None`` when the marker is
    correct or the line shape does not let us tell.

    The comment-marker prefix (or html/c-block wrapper) determines which
    variant the header *was* written in.
    """
    stripped = observed_line.lstrip()
    if target_variant == VARIANT_HTML:
        if not stripped.startswith("<!--"):
            return "missing <!-- wrapper"
        return None
    if target_variant == VARIANT_C_BLOCK:
        if not stripped.startswith("/*"):
            return "missing /* wrapper"
        return None

    target_prefix_map = {
        VARIANT_HASH: "#",
        VARIANT_DOUBLE_SLASH: "//",
        VARIANT_SEMICOLON: ";",
        VARIANT_DOUBLE_DASH: "--",
    }
    target_prefix = target_prefix_map.get(target_variant)
    if target_prefix is None:
        return None
    if not stripped.startswith(target_prefix):
        # Sniff which marker the line uses instead.
        for sniff_prefix in ("//", "--", ";", "#", "<!--", "/*"):
            if stripped.startswith(sniff_prefix):
                return sniff_prefix
        return "unrecognized marker"
    return None


# ---------------------------------------------------------------------------
# Injection-plan emission.
# ---------------------------------------------------------------------------
def build_injection_plan(
    relative_path: str,
    head_lines: list[str],
    header_status: str,
    variant: str,
    header_line_range: tuple[int, int] | None,
) -> dict[str, object] | None:
    """Return the unified-diff-bearing injection plan for an absent or
    malformed banner; ``None`` when no action is required.
    """
    if header_status == HEADER_PRESENT_CANONICAL:
        return None
    if header_status == HEADER_NOT_APPLICABLE:
        return None
    if variant == VARIANT_EXEMPT:
        return None

    canonical_lines = canonical_banner_lines(variant)
    insert_at = insertion_line(head_lines)

    if header_status == HEADER_ABSENT:
        action = "insert"
        before_lines = list(head_lines)
        # Insertion: shebang preserved at line 1; banner begins at
        # `insert_at`; existing content shifts down. A single blank
        # separator follows the banner.
        after_lines: list[str] = []
        for idx, line in enumerate(before_lines, start=1):
            if idx == insert_at:
                after_lines.extend(canonical_lines)
                after_lines.append("")
                after_lines.append(line)
            else:
                after_lines.append(line)
        if not before_lines:
            after_lines = list(canonical_lines)
            after_lines.append("")
        replacement_lines = None
    else:
        # present-malformed — replace the malformed range with canonical.
        action = "replace"
        before_lines = list(head_lines)
        if header_line_range is None:
            return None
        start_1based, end_1based = header_line_range
        start_idx = start_1based - 1
        end_idx = end_1based  # slice is half-open
        after_lines = (
            before_lines[:start_idx] + canonical_lines + before_lines[end_idx:]
        )
        replacement_lines = [start_1based, end_1based]

    diff = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            n=DIFF_CONTEXT_LINES,
            lineterm="",
        )
    )

    truncated = False
    diff_text = "\n".join(diff)
    if len(diff_text) > 4_000:
        diff_text = diff_text[:4_000] + "\n[... diff truncated ...]"
        truncated = True

    return {
        "needed": True,
        "action": action,
        "insertion-line": insert_at if action == "insert" else None,
        "replacement-lines": replacement_lines,
        "diff": diff_text,
        "diff-truncated": truncated,
    }
