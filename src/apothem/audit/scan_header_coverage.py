# SPDX-License-Identifier: MIT

"""Detailed authorship-header coverage scan against the inventory snapshot.

Why this tool exists. The inventory pass at the prior audit phase carries
a coarse four-mark heuristic for the authorship banner — sufficient to
size the work, insufficient to drive an injector. The downstream banner
ratification, fixture authoring, validator authoring, and injection
passes need a per-file authoritative record: applicability per the
exception fixture, header-status by byte-precise comparison against the
canonical variant for the file's filetype family, the line range the
banner occupies (if present), the malformation class (if malformed),
and a per-file injection plan with a unified-diff preview. This tool
emits ``header-coverage.json`` and ``header-coverage.md`` once; the
operator-confirm and injection phases consume them.

What the tool captures. Per applicable file: ``path``, ``variant-family``
(one of ``hash`` / ``double-slash`` / ``html`` / ``c-block`` /
``semicolon`` / ``double-dash`` / ``exempt``), ``header-status`` (
``present-canonical`` / ``present-malformed`` / ``absent`` /
``not-applicable``), ``header-line-range`` (the inclusive 1-based span
the banner occupies, or ``null``), ``malformation-class`` (one of the
eight classification slots when ``present-malformed``), and an
``injection-plan`` block carrying the unified-diff preview the injector
would apply. Aggregates: counts by variant family, counts by
malformation class, coverage percentage (``present-canonical /
applicable-total``).

Scope boundary. The tool ONLY inspects file heads (the first sixty
lines, which absorbs every shebang + frontmatter + banner shape the
canonical variants emit) and ONLY reads bytes — it never writes the
banner. The injection pass at the downstream phase consumes this
output's diff previews and applies them.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Canonical header rendering lives in ``header_banner``, which mirrors
# src/apothem/conformity/file_header_grep.py byte-for-byte so the scanner, the
# validator, and the injector agree on the canonical form without sharing a
# module. Re-exported here: this module is the established public entry point.
# ---------------------------------------------------------------------------
from apothem.audit.header_banner import (
    canonical_banner_lines,
    # Public re-export: consumed through this module's path, not called here,
    # so the unused-import rule cannot see its importers.
    canonical_banner_text,  # noqa: F401
    canonical_block_lines,
)

# ---------------------------------------------------------------------------
# Shared vocabulary. The status / variant / malformation taxonomies, the
# path-to-variant maps, the detection markers, and the budgets live in
# ``header_vocabulary`` so each pipeline stage can name them without
# importing its sibling stages. Re-exported here: this module is the
# established public entry point for the whole header-coverage surface.
# ---------------------------------------------------------------------------
from apothem.audit.header_vocabulary import (
    ALL_MALFORMATIONS,
    ALL_VARIANTS,
    BASENAME_VARIANT,
    BOM_PREFIX,
    DIFF_CONTEXT_LINES,
    EXIT_ERROR,
    EXIT_OK,
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
    SUFFIX_VARIANT,
    VARIANT_C_BLOCK,
    VARIANT_DOUBLE_DASH,
    VARIANT_DOUBLE_SLASH,
    VARIANT_EXEMPT,
    VARIANT_HASH,
    VARIANT_HTML,
    VARIANT_SEMICOLON,
)


# ---------------------------------------------------------------------------
# Variant resolution.
# ---------------------------------------------------------------------------
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

    import re

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


# ---------------------------------------------------------------------------
# Per-file scan.
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class FileCoverage:
    """Per-file coverage record emitted to ``header-coverage.json``."""

    path: str
    applicable: bool
    exception_class: str | None
    header_status: str
    variant_family: str
    header_line_range: tuple[int, int] | None
    malformation_class: str | None
    malformation_detail: str | None
    injection_plan: dict[str, object] | None

    def to_json(self) -> dict[str, object]:
        """Return this report as a JSON-ready mapping.

        Post-conditions: the payload carries ``{path, applicable,
        exception-class, header-status, variant-family, header-line-range,
        malformation-class, malformation-detail, injection-plan}``.
        """
        return {
            "path": self.path,
            "applicable": self.applicable,
            "exception-class": self.exception_class,
            "header-status": self.header_status,
            "variant-family": self.variant_family,
            "header-line-range": (
                list(self.header_line_range) if self.header_line_range else None
            ),
            "malformation-class": self.malformation_class,
            "malformation-detail": self.malformation_detail,
            "injection-plan": self.injection_plan,
        }


@dataclass(slots=True)
class CoverageSummary:
    """Aggregate counts emitted alongside the per-file array."""

    total_files: int = 0
    applicable_total: int = 0
    present_canonical: int = 0
    present_malformed: int = 0
    absent: int = 0
    not_applicable: int = 0
    coverage_pct: float = 0.0
    by_variant_family: dict[str, int] = field(default_factory=dict)
    by_malformation_class: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        """Return this report as a JSON-ready mapping.

        Post-conditions: the payload carries ``{total-files, applicable-total,
        present-canonical, present-malformed, absent, not-applicable,
        coverage-pct, by-variant-family, by-malformation-class}``.
        """
        return {
            "total-files": self.total_files,
            "applicable-total": self.applicable_total,
            "present-canonical": self.present_canonical,
            "present-malformed": self.present_malformed,
            "absent": self.absent,
            "not-applicable": self.not_applicable,
            "coverage-pct": round(self.coverage_pct, 2),
            "by-variant-family": dict(sorted(self.by_variant_family.items())),
            "by-malformation-class": dict(sorted(self.by_malformation_class.items())),
        }


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


# ---------------------------------------------------------------------------
# Top-level scan.
# ---------------------------------------------------------------------------
def scan_inventory(
    inventory_path: Path,
    fixture_path: Path,
    root: Path,
) -> tuple[list[FileCoverage], CoverageSummary, dict[str, str]]:
    """Walk inventory records, classify every file, and emit coverage rows."""
    raw = inventory_path.read_bytes()
    inventory_sha = hashlib.sha256(raw).hexdigest()
    inventory = json.loads(raw.decode("utf-8"))
    records = inventory.get("files", [])

    fixture_bytes = fixture_path.read_bytes() if fixture_path.is_file() else b""
    fixture_sha = hashlib.sha256(fixture_bytes).hexdigest() if fixture_bytes else ""
    globs = load_exception_globs(fixture_path)

    rows: list[FileCoverage] = []
    summary = CoverageSummary(total_files=len(records))
    for variant in ALL_VARIANTS:
        summary.by_variant_family[variant] = 0
    for malform in ALL_MALFORMATIONS:
        summary.by_malformation_class[malform] = 0

    for record in records:
        rel_path = str(record.get("path", ""))
        if not rel_path:
            continue
        absolute = root / rel_path
        relative_obj = Path(rel_path)

        # Applicability: the exception fixture is the authoritative gate.
        # A path matching any pattern is `not-applicable`. Otherwise the
        # variant family resolution decides whether the file's filetype
        # carries a banner at all.
        exception_class = matches_exception(rel_path, globs)
        variant = variant_family_for(relative_obj)

        if exception_class is not None or variant == VARIANT_EXEMPT:
            row = FileCoverage(
                path=rel_path,
                applicable=False,
                exception_class=exception_class
                or (None if variant != VARIANT_EXEMPT else "unsupported-extension"),
                header_status=HEADER_NOT_APPLICABLE,
                variant_family=variant,
                header_line_range=None,
                malformation_class=None,
                malformation_detail=None,
                injection_plan=None,
            )
            rows.append(row)
            summary.not_applicable += 1
            summary.by_variant_family[variant] += 1
            continue

        head = read_head(absolute)
        status, line_range, malform, detail = scan_for_banner(head, variant)
        plan = build_injection_plan(rel_path, head, status, variant, line_range)

        row = FileCoverage(
            path=rel_path,
            applicable=True,
            exception_class=None,
            header_status=status,
            variant_family=variant,
            header_line_range=line_range,
            malformation_class=malform,
            malformation_detail=detail,
            injection_plan=plan,
        )
        rows.append(row)
        summary.applicable_total += 1
        summary.by_variant_family[variant] += 1
        if status == HEADER_PRESENT_CANONICAL:
            summary.present_canonical += 1
        elif status == HEADER_PRESENT_MALFORMED:
            summary.present_malformed += 1
            if malform is not None:
                summary.by_malformation_class[malform] += 1
        elif status == HEADER_ABSENT:
            summary.absent += 1
        else:
            summary.not_applicable += 1

    if summary.applicable_total > 0:
        summary.coverage_pct = (
            100.0 * summary.present_canonical / summary.applicable_total
        )

    provenance = {
        "inventory-source": str(inventory_path),
        "inventory-sha256": inventory_sha,
        "exception-fixture-source": str(fixture_path),
        "exception-fixture-sha256": fixture_sha,
    }
    return rows, summary, provenance


# ---------------------------------------------------------------------------
# Markdown mirror emission.
# ---------------------------------------------------------------------------
def render_markdown(
    rows: list[FileCoverage],
    summary: CoverageSummary,
    provenance: dict[str, str],
    generated_at: str,
) -> str:
    """Render the human-readable coverage mirror."""
    lines: list[str] = []
    lines.append("# Authorship-Header Coverage Map")
    lines.append("")
    lines.append(f"- **Generated:** {generated_at}")
    lines.append(f"- **Inventory source:** `{provenance['inventory-source']}`")
    lines.append(f"- **Inventory SHA-256:** `{provenance['inventory-sha256']}`")
    lines.append(f"- **Exception fixture:** `{provenance['exception-fixture-source']}`")
    lines.append(
        f"- **Exception fixture SHA-256:** `{provenance['exception-fixture-sha256']}`"
    )
    lines.append("")
    lines.append("## Aggregate Statistics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Total files inventoried | {summary.total_files} |")
    lines.append(f"| Applicable | {summary.applicable_total} |")
    lines.append(f"| Present (canonical) | {summary.present_canonical} |")
    lines.append(f"| Present (malformed) | {summary.present_malformed} |")
    lines.append(f"| Absent | {summary.absent} |")
    lines.append(f"| Not applicable | {summary.not_applicable} |")
    lines.append(f"| Coverage % | {summary.coverage_pct:.2f}% |")
    lines.append("")

    lines.append("## Counts by Variant Family")
    lines.append("")
    lines.append("| Variant family | Count |")
    lines.append("|---|---:|")
    for variant in ALL_VARIANTS:
        lines.append(f"| `{variant}` | {summary.by_variant_family.get(variant, 0)} |")
    lines.append("")

    lines.append("## Counts by Malformation Class")
    lines.append("")
    lines.append("| Malformation class | Count |")
    lines.append("|---|---:|")
    for malform in ALL_MALFORMATIONS:
        lines.append(
            f"| `{malform}` | {summary.by_malformation_class.get(malform, 0)} |"
        )
    lines.append("")

    # Per-file injection-plan tables, partitioned by status.
    absent_rows = [r for r in rows if r.header_status == HEADER_ABSENT]
    malformed_rows = [r for r in rows if r.header_status == HEADER_PRESENT_MALFORMED]
    canonical_rows = [r for r in rows if r.header_status == HEADER_PRESENT_CANONICAL]

    if canonical_rows:
        lines.append(f"## Files with Canonical Banner ({len(canonical_rows)})")
        lines.append("")
        lines.append("| Path | Variant | Lines |")
        lines.append("|---|---|---|")
        for row in sorted(canonical_rows, key=lambda r: r.path):
            rng = (
                f"{row.header_line_range[0]}-{row.header_line_range[1]}"
                if row.header_line_range
                else "—"
            )
            lines.append(f"| `{row.path}` | `{row.variant_family}` | {rng} |")
        lines.append("")

    if malformed_rows:
        lines.append(f"## Files with Malformed Banner ({len(malformed_rows)})")
        lines.append("")
        lines.append("| Path | Variant | Lines | Class | Detail |")
        lines.append("|---|---|---|---|---|")
        for row in sorted(malformed_rows, key=lambda r: r.path):
            rng = (
                f"{row.header_line_range[0]}-{row.header_line_range[1]}"
                if row.header_line_range
                else "—"
            )
            detail = (row.malformation_detail or "").replace("|", r"\|")
            lines.append(
                f"| `{row.path}` | `{row.variant_family}` | {rng} | "
                f"`{row.malformation_class}` | {detail} |"
            )
        lines.append("")

    if absent_rows:
        lines.append(f"## Files Missing the Banner ({len(absent_rows)})")
        lines.append("")
        lines.append("| Path | Variant | Insertion line |")
        lines.append("|---|---|---:|")
        for row in sorted(absent_rows, key=lambda r: r.path):
            ip = row.injection_plan
            insertion = (
                str(ip.get("insertion-line"))
                if isinstance(ip, dict) and ip.get("insertion-line") is not None
                else "—"
            )
            lines.append(f"| `{row.path}` | `{row.variant_family}` | {insertion} |")
        lines.append("")

    # Sample injection-plan diffs (first three of each non-trivial class).
    sample_rows = (malformed_rows + absent_rows)[:6]
    if sample_rows:
        lines.append("## Sample Injection-Plan Diffs")
        lines.append("")
        for row in sample_rows:
            ip = row.injection_plan
            if not isinstance(ip, dict):
                continue
            lines.append(
                f"### `{row.path}` — {row.header_status} / `{row.variant_family}`"
            )
            lines.append("")
            lines.append("```diff")
            diff_text = str(ip.get("diff", ""))
            for diff_line in diff_text.splitlines()[:30]:
                lines.append(diff_line)
            if len(diff_text.splitlines()) > 30:
                lines.append("[... truncated for readability ...]")
            lines.append("```")
            lines.append("")

    # Exception-class breakdown so the operator can audit the fixture's
    # reach.
    not_applicable_rows = [r for r in rows if r.header_status == HEADER_NOT_APPLICABLE]
    if not_applicable_rows:
        lines.append(f"## Files Marked Not Applicable ({len(not_applicable_rows)})")
        lines.append("")
        from collections import Counter

        class_counts = Counter(
            r.exception_class or "no-fixture-match" for r in not_applicable_rows
        )
        lines.append("| Exception class | Count |")
        lines.append("|---|---:|")
        for cls, count in class_counts.most_common():
            lines.append(f"| `{cls}` | {count} |")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the CLI argument vector."""
    parser = argparse.ArgumentParser(
        description=(
            "Detailed authorship-header coverage scan against the inventory "
            "snapshot. Emits header-coverage.json and header-coverage.md."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Working-tree root (defaults to the current directory).",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
        help="Path to inventory.json (relative to --root or absolute).",
    )
    parser.add_argument(
        "--exception-fixture",
        type=Path,
        default=Path("src/apothem/schemas/header-exceptions.txt"),
        help="Path to the exception-list glob fixture.",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path(".audit/header-coverage.json"),
        help="Output path for the machine-readable coverage record.",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path(".audit/header-coverage.md"),
        help="Output path for the human-readable coverage mirror.",
    )
    return parser.parse_args(argv)


def resolve_path(root: Path, candidate: Path) -> Path:
    """Resolve ``candidate`` against ``root`` when it is relative."""
    return candidate if candidate.is_absolute() else root / candidate


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — orchestrate the scan and emit outputs."""
    args = parse_args(argv)
    root = args.root.resolve()
    inventory_path = resolve_path(root, args.inventory)
    fixture_path = resolve_path(root, args.exception_fixture)
    out_json = resolve_path(root, args.out_json)
    out_md = resolve_path(root, args.out_md)

    if not inventory_path.is_file():
        print(
            f"error: inventory not found at {inventory_path}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    rows, summary, provenance = scan_inventory(inventory_path, fixture_path, root)

    generated_at = datetime.now(timezone.utc).isoformat()
    payload: dict[str, object] = {
        "scanner": "scan_header_coverage",
        "scanner-version": "1.0.0",
        "generated-at": generated_at,
        "root": str(root),
        **provenance,
        "summary": summary.to_json(),
        "files": [row.to_json() for row in rows],
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        render_markdown(rows, summary, provenance, generated_at),
        encoding="utf-8",
    )

    print(
        f"scan_header_coverage: {summary.applicable_total} applicable, "
        f"{summary.present_canonical} canonical "
        f"({summary.coverage_pct:.2f}%), "
        f"{summary.present_malformed} malformed, "
        f"{summary.absent} absent, "
        f"{summary.not_applicable} not-applicable",
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
