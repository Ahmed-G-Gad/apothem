# SPDX-License-Identifier: MIT

"""Cross-file binding-reciprocity corpus walk — the ↔-symmetric half-edge check.

Why this enforcement exists. The bidirectional-binding rule M10 (§2) declares
that every binding is reciprocal: when rule A's Bindings cite rule B under
``Cross-bound with ↔``, rule B's Bindings MUST cite rule A under the same
``Cross-bound with ↔`` direction — the self-reciprocal direction the rule
names as "the only one that requires identical wording on both ends". A cite
without its reciprocal is a **half-edge**, a structural failure. The per-file
``binding_reciprocity_grep`` matcher enforces the arrow *notation* within a
single Bindings section; it cannot see across files. This standalone validator
is the corpus counterpart the per-file grep's docstring defers to: it walks the
whole ``rules/`` corpus, extracts every ``Cross-bound with ↔`` citation to a
sibling ``rules/*.md`` file, and reports every half-edge (A cites B; B does not
cite A back under ↔).

Scope — ↔-symmetric only. This validator enforces the SYMMETRIC relation
alone: the ``Cross-bound with ↔`` direction, whose reciprocal is the same
direction on the peer (per M10 §2 the self-reciprocal direction). The
directional relations (``Drives →`` / ``Driven by ←``, ``Satisfies →`` /
``Established by ↑``) are NOT checked here — M10 specifies their reciprocity in
prose, but the rule-set's live convention does not thread those directions
between ``rules/*.md`` peers with the regularity the ↔ direction carries (a
rule's ``Drives →`` targets are typically artifacts, gate rows, and downstream
surfaces, not sibling rules that reciprocate with ``Driven by ←``), so a
directional check would be dominated by legitimate asymmetry rather than
defects. The ↔ relation is the mechanically-clean, unambiguously-symmetric edge
the corpus threads rule-to-rule, and it is the edge a rules-consolidation must
keep closed.

Scope — rule-to-rule edges only. Only ``rules/<name>.md`` → ``rules/<name>.md``
citations are considered. A ``Cross-bound with ↔`` citation to a non-rule
surface (``conformity/*.py``, ``skills/<name>/SKILL.md``, ``hooks/...``, a
``.github/workflows/*.yml`` drift-gate arm) is ignored: those surfaces carry no
Bindings section and are not subject to reciprocity. Name resolution is by
basename — the citation ``rules/token-budget-discipline.md`` resolves to the
``token-budget-discipline`` rule regardless of any path prefix.

Posture — blocking. The rules corpus ships with every ↔ edge closed (the
2026-07 reciprocity consolidation added the reciprocal citation at every
half-edge's target end), so the check gates: a new half-edge fails the
validator, ``gate --all --strict`` exits non-zero on it, and the CLI exits
``EXIT_FAIL``. The closure protocol in the bidirectional-binding rule §2
applies — a patch adding a ``Cross-bound with ↔`` citation lands the
reciprocal at the cited rule in the same change-set.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import (
    EXIT_FAIL,
    EXIT_PASS,
    RootGrepResult,
    iter_prose_lines,
    read_root,
)

__all__ = ["EXIT_FAIL", "EXIT_PASS", "Finding", "check"]

GREP_NAME: Final[str] = "binding-reciprocity-corpus-grep"
RULE_ANCHOR: Final[str] = "M10 bidirectional-binding §2 (↔ self-reciprocal)"

# The rules corpus lives at ``<root>/src/apothem/rules`` in a repo checkout and
# at ``<root>/rules`` in an installed harness tree; the walk tries both so the
# validator resolves the corpus from either layout.
_RULES_SUBTREES: Final[tuple[tuple[str, ...], ...]] = (
    ("src", "apothem", "rules"),
    ("rules",),
)

# The canonical Bindings-section heading — the same form the per-file
# ``binding_reciprocity_grep`` accepts (with or without the parenthetical).
_BINDINGS_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+Bindings(?:\s+\(§0\.j\s+five-direction\))?\s*$"
)
_NEXT_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##?\s+\S")

# Fenced-code delimiter. ``bidirectional-binding.md`` (and any rule quoting the
# Bindings shape) carries a fenced ``## Bindings`` EXAMPLE block in its body; a
# heading / citation inside a fence is illustrative, not the artifact's own
# Bindings section, so the walk toggles a fence flag and skips fenced lines when
# locating and reading the section. The column-0 form matches the ``` fence the
# rule bodies use.
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^```")

# A direction bullet opens with a bold label carrying its canonical arrow, e.g.
# ``- **Cross-bound with ↔** ...`` or ``- **Drives →** ...``. The arrow may sit
# inside the bold span (``**Cross-bound with ↔**``) per the canonical form. The
# label text (sans arrow) is captured so the ``Cross-bound`` direction is
# identified regardless of the exact arrow glyph.
_DIRECTION_BULLET_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*[-*]\s*\*\*\s*(?P<label>[^*]+?)\s*\*\*"
)

# A citation to a sibling rule file. The basename is captured; any path prefix
# (``rules/``, ``../rules/``, a bare name is not matched — the ``rules/`` anchor
# is required so a stray ``foo.md`` mention is not read as a rule citation).
_RULE_CITATION_RE: Final[re.Pattern[str]] = re.compile(
    r"`[^`]*?rules/(?P<name>[A-Za-z0-9][A-Za-z0-9-]*)\.md`"
)

# The direction whose reciprocal is itself (symmetric). Matched on the label
# text with the arrow stripped, case-insensitively, so ``Cross-bound with``
# identifies the direction whether or not the arrow rendered inside the bold.
_CROSS_BOUND_LABEL: Final[str] = "cross-bound with"


@dataclass(frozen=True)
class Finding:
    """One ↔ half-edge: *source* cites *target* under ↔; *target* does not cite back."""

    source: str
    target: str
    detail: str
    rule: str = RULE_ANCHOR


def _resolve_rules_dir(root: Path) -> Path | None:
    """Return the rules corpus directory under *root*, or None when absent.

    Tries the repo-checkout layout (``src/apothem/rules``) first, then the
    installed-tree layout (``rules``); returns the first that is a directory.
    """
    for parts in _RULES_SUBTREES:
        candidate = root.joinpath(*parts)
        if candidate.is_dir():
            return candidate
    return None


def _bindings_lines(text: str) -> list[str]:
    """Return the non-fenced lines inside the artifact's own Bindings section.

    The walk is fence-aware: a ``## Bindings`` heading (or a citation) inside a
    fenced code block is an EXAMPLE — ``bidirectional-binding.md`` carries a
    fenced Bindings shape in its §1 body — not the artifact's real Bindings
    section, so fenced lines are skipped entirely. The real section begins after
    the first NON-fenced ``## Bindings`` heading and ends at the next non-fenced
    H1/H2 heading (or end-of-file). An artifact with no Bindings section outside
    a fence yields an empty list. ``iter_prose_lines`` toggles the fence flag and
    yields only non-fenced lines, matching the sibling per-file matcher's
    fence-exclusion behaviour.
    """
    collected: list[str] = []
    started = False
    for _lineno, raw_line, _scanned in iter_prose_lines(
        text.splitlines(), fence_re=_CODE_FENCE_RE
    ):
        if not started:
            if _BINDINGS_HEADING_RE.match(raw_line):
                started = True
            continue
        if _NEXT_HEADING_RE.match(raw_line):
            break
        collected.append(raw_line)
    return collected


def _cross_bound_citations(text: str) -> set[str]:
    """Return the sibling-rule basenames cited under ``Cross-bound with ↔``.

    Walks the Bindings section, tracking the active direction bullet: a line
    opening a ``Cross-bound with`` bullet switches the active direction on, and
    a line opening any other direction bullet switches it off. Every
    ``rules/<name>.md`` citation on a line while the ↔ direction is active
    contributes its basename. Continuation lines (a wrapped citation list with
    no new bold label) inherit the active direction, so a multi-line ↔ bullet is
    fully captured.
    """
    names: set[str] = set()
    in_cross_bound = False
    for line in _bindings_lines(text):
        bullet = _DIRECTION_BULLET_RE.match(line)
        if bullet is not None:
            label = bullet.group("label").strip().lower()
            # Strip any trailing arrow glyph left inside the label capture.
            label = label.rstrip("→←↑↓↔ ").strip()
            in_cross_bound = label.startswith(_CROSS_BOUND_LABEL)
        if in_cross_bound:
            for match in _RULE_CITATION_RE.finditer(line):
                names.add(match.group("name"))
    return names


def check(root: Path) -> RootGrepResult:
    """Walk the rules corpus; report every ↔-symmetric half-edge.

    Pre-conditions: *root* is a repository root or an installed harness tree
    carrying a rules corpus at ``src/apothem/rules`` or ``rules``.
    Post-conditions: for every ordered pair (A, B) where A's Bindings cite
    ``rules/B.md`` under ``Cross-bound with ↔`` and B is a real rule in the
    corpus, a finding is emitted iff B's Bindings do NOT cite ``rules/A.md``
    under ``Cross-bound with ↔``. Only rule-to-rule edges are considered;
    citations to non-rule surfaces and to rules absent from the corpus are
    skipped. ``result.passed`` is True iff no half-edge is found. The result is
    advisory (``advisory=True``): the CLI always exits 0.
    """
    rules_dir = _resolve_rules_dir(root)
    if rules_dir is None:
        # No corpus to walk (a subtree without the rules tree, a shallow layout);
        # a clean pass — there is nothing to check.
        return RootGrepResult(
            grep=GREP_NAME,
            root=str(root),
            passed=True,
        )

    # basename -> set of ↔-cited sibling-rule basenames.
    cross_map: dict[str, set[str]] = {}
    for md in sorted(rules_dir.glob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        cross_map[md.stem] = _cross_bound_citations(text)

    corpus = frozenset(cross_map)
    findings: list[Finding] = []
    for source in sorted(cross_map):
        for target in sorted(cross_map[source]):
            if target == source:
                # Self-citation is not a binding per M10 §4 (the matrix diagonal
                # is ``—``); ignore rather than flag.
                continue
            if target not in corpus:
                # Citation to a name that is not a real rule in the corpus —
                # out of scope (a non-rule surface, or a stale/renamed target
                # the naming/link matchers own).
                continue
            if source not in cross_map[target]:
                findings.append(
                    Finding(
                        source=f"rules/{source}.md",
                        target=f"rules/{target}.md",
                        detail=(
                            f"'rules/{source}.md' cites 'rules/{target}.md' under "
                            f"'Cross-bound with ↔', but 'rules/{target}.md' does not "
                            f"cite 'rules/{source}.md' back under 'Cross-bound with ↔' "
                            "— a ↔ half-edge; add the reciprocal citation at the "
                            "target's Bindings section in the same change-set"
                        ),
                    )
                )

    return RootGrepResult(
        grep=GREP_NAME,
        root=str(root),
        passed=not findings,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    root = read_root(argv)
    result = check(root)
    print(result.to_json())
    # Blocking posture: the corpus ships green, so a half-edge is a gating
    # regression — mirror the standard grep exit contract (EXIT_PASS on a
    # clean walk, EXIT_FAIL on any finding).
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
