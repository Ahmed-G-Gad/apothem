# SPDX-License-Identifier: MIT

"""Flag substantively-duplicated paragraphs across the governed corpus.

Why this enforcement exists. Spec section 3.1.e enumerates a five-class
redundancy taxonomy that erodes the demand-load discipline: (a)
parent-rule / companion sub-rule overlap, (b) cross-rule conceptual
duplication, (c) command / skill content overlap, (d) hook / rule
duplication, and (e) example duplication across docs. Each class
multiplies maintenance cost — a single edit must reach every duplicate
or the corpus drifts.

Detection strategy. The validator walks the four canonical authoring
trees (``rules/``, ``commands/``, ``skills/``, ``hooks/messages/``),
splits every Markdown file into paragraphs on blank-line boundaries,
normalises each paragraph (lowercase, collapse whitespace, strip
punctuation), tokenises into a set, and compares pairwise across files
using Jaccard similarity. Two paragraphs above ``--threshold`` (default
0.80) AND carrying at least 40 substantive tokens are reported as a
duplication finding with the participating file paths and a suggested
canonical home (the file whose path prefix sorts earliest, as a
deterministic-but-reviewable hint — the operator picks the real
canonical home).

Scope carve-outs. Lines opening with ``(Companion Sub-Rule Anchor)`` are
EXPLICIT delegation pointers and are excluded from comparison. Fenced
code blocks are excluded (sample inputs and command snippets quote
external material rather than carry the author's prescriptive prose).
YAML frontmatter is excluded. The ``## Bindings`` tail section is
excluded — reciprocal binding statements legitimately overlap by
construction.

Heuristic-status disclaimer. Jaccard on tokenised paragraphs is a
heuristic. False positives are expected on canonical templates (banner
lines, gate attestation skeletons, common preambles). The operator
triages each finding; the threshold flag exists so a tighter or looser
gate can be tuned per corpus state without code changes.

Exit semantics. Exits 0 when no findings; exits 2 on any finding.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "redundancy-grep"
RULE_ANCHOR: Final[str] = (
    "rules/operational-mandates.md §CM-7 coherent-product non-redundancy"
)

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Canonical authoring trees the validator walks. The relative roots are
# resolved against the project root passed on the command line.
CORPUS_SUBTREES: Final[tuple[str, ...]] = (
    "src/apothem/rules",
    "src/apothem/commands",
    "src/apothem/skills",
    "src/apothem/hooks/messages",
)

# Default Jaccard similarity threshold above which two paragraphs are
# reported as duplicates. Tuneable via --threshold.
DEFAULT_THRESHOLD: Final[float] = 0.80

# Minimum substantive token count for a paragraph to enter comparison.
# Shorter paragraphs (headings, one-liners, brief bullets) carry too
# little signal for Jaccard to discriminate genuine duplication from
# coincidental phrase overlap.
MIN_SUBSTANTIVE_TOKENS: Final[int] = 40

# Fenced code-block delimiter and frontmatter delimiter.
_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^```")
_FRONTMATTER_DELIM: Final[str] = "---"

# Companion-anchor pointer marker — excluded from comparison.
_COMPANION_ANCHOR_MARKER: Final[str] = "(Companion Sub-Rule Anchor)"

# Bindings tail section header. Everything from this header to EOF is
# excluded from the comparison surface.
_BINDINGS_HEADER_RE: Final[re.Pattern[str]] = re.compile(
    r"^##+\s*Bindings\b", re.MULTILINE
)

# Markdown ATX heading recogniser. Captures the heading level (count of
# leading '#') and the title text.
_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

# Canonical-scaffolding heading allow-list. Paragraphs whose enclosing
# heading (or any ancestor heading in the section hierarchy) contains any
# of these substrings as a heading title are excluded from comparison.
# The blocks under these headings are canonical-by-design — the same
# voice / contract / pipeline-position prose appears uniformly across
# every audit-fortress and plan-pipeline command and across every
# header-guard hook message, per `skills/ecosystem-audit/SKILL.md`
# Audit-Fortress Phase Skeleton and the operator-ratified canonical
# scaffolding pattern. Generic redundancy-grep flagging would force
# stripping the uniformity that the canonical scaffolding requires.
# Match is case-insensitive substring.
_SCAFFOLDING_HEADING_SUBSTRINGS: Final[tuple[str, ...]] = (
    "pipeline contract",
    "foundational stanzas",
    "refusal & escalation",
    "output surface",
    "file-authoring contract",
    "askuserquestion on ambiguity",
    "inquiry cadence",
    "audit-fortress",
    "critical rules",
    "mandates",
    "findings report shape",
    "axis-of-attention",
    "axis attestation",
    "borderline triage",
    "severity triage",
    "pre-emission gate",
    "output discipline",
    "inquiry triage",
    "scope clarification",
    # `## Resolution & Recovery` carries the canonical template/surface
    # corruption-fallback contract that every pipeline suite-skill states in
    # uniform voice (plan-suite cites TM-N/CP-N IDs, research-suite cites the
    # R-mandate/lifecycle IDs) — same scaffolding class as "refusal &
    # escalation"; per-pipeline specialisation lives in the prose, so the
    # blocks stay self-contained rather than cross-referencing one another.
    "resolution & recovery",
)

# Punctuation stripper for token normalisation.
_PUNCT_RE: Final[re.Pattern[str]] = re.compile(r"[^\w\s]+")


@dataclass(frozen=True)
class Finding:
    """One near-duplicate prose block spanning two or more documents.

    Pre-conditions: ``files`` lists every path carrying the duplicated block;
    ``similarity`` is the measured ratio that crossed the sweep's threshold;
    ``suggested_canonical_home`` names the single file the block should live in
    so the others can cross-reference it instead of restating it. ``issue`` and
    ``detail`` carry the operator-facing classification and excerpt.
    Post-conditions: ``rule`` defaults to :data:`RULE_ANCHOR`, citing the
    non-redundancy discipline the duplication violates.
    """

    issue: str
    detail: str
    files: list[str]
    similarity: float
    suggested_canonical_home: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Matcher report for a single sweep of this validator.

    Carries its own result shape rather than reusing the shared base because
    the payload adds ``threshold``, ``paragraph_count``.

    Pre-conditions: ``findings`` holds this module's frozen ``Finding``
    dataclasses. Post-conditions: ``passed`` is ``True`` exactly when
    ``findings`` is empty; :meth:`to_json` emits the serialised payload.
    """

    grep: str
    root: str
    threshold: float
    paragraph_count: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, threshold,
        paragraph_count, passed, findings}``; each finding is flattened through
        ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "threshold": self.threshold,
            "paragraph_count": self.paragraph_count,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _strip_frontmatter(text: str) -> str:
    """Remove leading YAML frontmatter, if present."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return text
    for idx in range(1, len(lines)):
        if lines[idx].strip() == _FRONTMATTER_DELIM:
            return "\n".join(lines[idx + 1 :])
    return text


def _strip_bindings_tail(text: str) -> str:
    """Trim everything from the first `## Bindings` header to EOF."""
    match = _BINDINGS_HEADER_RE.search(text)
    if match is None:
        return text
    return text[: match.start()]


def _strip_fenced_code(text: str) -> str:
    """Remove fenced code blocks; the surrounding prose remains."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def _is_scaffolding_heading(title: str) -> bool:
    """Return True iff the heading title matches any canonical-scaffolding
    allow-list substring (case-insensitive)."""
    lowered = title.lower()
    return any(sub in lowered for sub in _SCAFFOLDING_HEADING_SUBSTRINGS)


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank-line boundaries; drop companion-anchor pointers and
    paragraphs whose enclosing heading hierarchy includes a
    canonical-scaffolding allow-listed section.

    The walker tracks the current heading stack: each ATX heading
    establishes the title at its level and clears every deeper level.
    A paragraph is excluded when any active heading in the stack matches
    the scaffolding allow-list.
    """
    out: list[str] = []
    heading_stack: dict[int, str] = {}
    current_block: list[str] = []

    def flush_block() -> None:
        """Close the accumulated paragraph and keep it when it is comparable.

        Post-conditions: the buffered lines are joined and appended to the
        comparison set, then cleared. A paragraph is dropped rather than
        appended when it is empty, when it carries the companion-anchor
        marker, or when any enclosing heading is on the scaffolding
        allow-list — those repeat legitimately and would otherwise register as
        false duplication.
        """
        if not current_block:
            return
        para = "\n".join(current_block).strip()
        current_block.clear()
        if not para:
            return
        if _COMPANION_ANCHOR_MARKER in para:
            return
        if any(_is_scaffolding_heading(title) for title in heading_stack.values()):
            return
        out.append(para)

    for line in text.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush_block()
            level = len(heading_match.group(1))
            title = heading_match.group(2)
            heading_stack[level] = title
            for deeper in [k for k in heading_stack if k > level]:
                del heading_stack[deeper]
            continue
        if not line.strip():
            flush_block()
            continue
        current_block.append(line)
    flush_block()
    return out


def _tokenise(paragraph: str) -> frozenset[str]:
    """Lowercase, strip punctuation, split on whitespace; return token set."""
    normalised = _PUNCT_RE.sub(" ", paragraph.lower())
    return frozenset(tok for tok in normalised.split() if tok)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _walk_corpus(root: Path) -> list[Path]:
    """Return every `.md` file under the four canonical subtrees."""
    files: list[Path] = []
    for sub in CORPUS_SUBTREES:
        base = root / sub
        if not base.exists():
            continue
        files.extend(sorted(base.rglob("*.md")))
    return files


def _extract_paragraphs(path: Path) -> list[tuple[str, frozenset[str]]]:
    """Return (text, token-set) pairs for every comparable paragraph."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    text = _strip_frontmatter(raw)
    text = _strip_bindings_tail(text)
    text = _strip_fenced_code(text)
    out: list[tuple[str, frozenset[str]]] = []
    for para in _split_paragraphs(text):
        tokens = _tokenise(para)
        if len(tokens) < MIN_SUBSTANTIVE_TOKENS:
            continue
        out.append((para, tokens))
    return out


def _are_sibling_variants(path_a: Path, path_b: Path) -> bool:
    """Return True iff two files are canonical sibling variants.

    Two files in the same directory whose stems differ in exactly one
    kebab-token position (e.g., ``pretooluse-edit-header-guard`` vs.
    ``pretooluse-write-header-guard``) or where one stem is a strict
    prefix of the other (parent / companion form,
    e.g., ``sota-elevation`` vs. ``sota-elevation-exemplars``) are
    canonical sibling variants. Their shared content IS the
    design — the matcher excludes pairings between them.
    """
    if path_a.parent != path_b.parent:
        return False
    tokens_a = path_a.stem.split("-")
    tokens_b = path_b.stem.split("-")
    if tokens_a == tokens_b:
        return False
    # Parent / companion: one is a strict prefix of the other.
    shorter, longer = sorted([tokens_a, tokens_b], key=len)
    if longer[: len(shorter)] == shorter:
        return True
    # Equal length: differ in exactly one position.
    if len(tokens_a) == len(tokens_b):
        differences = sum(1 for a, b in zip(tokens_a, tokens_b, strict=True) if a != b)
        return differences == 1
    return False


def check_corpus(root: Path, threshold: float = DEFAULT_THRESHOLD) -> GrepResult:
    """Walk the corpus; report duplicated paragraphs above ``threshold``."""
    files = _walk_corpus(root)
    # Flatten to (path, paragraph_text, tokens) tuples.
    entries: list[tuple[Path, str, frozenset[str]]] = []
    for f in files:
        for text, tokens in _extract_paragraphs(f):
            entries.append((f, text, tokens))
    findings: list[Finding] = []
    seen_pairs: set[tuple[int, int]] = set()
    for i in range(len(entries)):
        path_i, text_i, tokens_i = entries[i]
        for j in range(i + 1, len(entries)):
            path_j, _text_j, tokens_j = entries[j]
            if path_i == path_j:
                continue
            if _are_sibling_variants(path_i, path_j):
                continue
            sim = _jaccard(tokens_i, tokens_j)
            if sim < threshold:
                continue
            key = (i, j)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            files_pair = sorted({path_i.as_posix(), path_j.as_posix()})
            canonical_home = files_pair[0]
            preview = text_i.replace("\n", " ").strip()
            if len(preview) > 160:
                preview = preview[:157] + "..."
            findings.append(
                Finding(
                    issue="substantively-duplicated paragraph",
                    detail=(
                        f"paragraph with jaccard similarity {sim:.2f} "
                        f"appears across {len(files_pair)} files; "
                        f"preview: {preview!r}"
                    ),
                    files=files_pair,
                    similarity=round(sim, 4),
                    suggested_canonical_home=canonical_home,
                )
            )
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        threshold=threshold,
        paragraph_count=len(entries),
        passed=not findings,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top: ``check_corpus()`` stays stdlib-only;
    # only the command-line entry needs the shared parser and report stamp.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    def _configure(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--threshold",
            type=float,
            default=DEFAULT_THRESHOLD,
            help=f"jaccard similarity threshold (default: {DEFAULT_THRESHOLD})",
        )

    args = parse_root_args(argv, prog=GREP_NAME, doc=__doc__, configure=_configure)
    result = check_corpus(args.root, threshold=args.threshold)
    return finish_root_report(
        result.to_json(), passed=result.passed, inspected=result.paragraph_count
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
