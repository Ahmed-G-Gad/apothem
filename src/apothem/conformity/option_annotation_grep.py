# SPDX-License-Identifier: MIT

"""Enforce the per-option Recommended label-to-body bind (H6).

Why this enforcement exists. Option sets surfaced for operator decision
annotate the recommended path so the operator sees the agent's share of
evaluation. The canonical-channel rule §3 binds each option's label to its
body: an option whose body `recommendation:` value is exactly `recommended`
carries the canonical `(Recommended)` postfix on its own label; no option
carries the postfix without the matching body value; and a single-select
question recommends at most one option. The prior file-wide "any one marker
anywhere" check accepted a body-only or rationale-only recommendation — this
matcher tightens that to a per-option bind so the marker lands on the right
label.

Canonical postfix. The canonical postfix string is capital `(Recommended)`
per `_spec/spec.md` §4.2 and `rules/interactive-questions-canonical-shapes.md`
§2.1; it is recognized case-correctly. The lowercase `(recommended)` form is a
banned variant and is itself a finding when it appears as a label postfix.

Detection strategy. An option is a label line — backtick form
``- `Label`:`` or YAML form ``label: Label`` — whose body (the lines up to the
next label) carries a `recommendation:` taxonomy value. For each option the
matcher computes two booleans (label-carries-canonical-postfix,
body-is-recommended) and flags every direction of the bind violation.
Cardinality is checked per invocation block (options grouped by the nearest
preceding invocation head — a prose channel mention or a canonical YAML
`question:` field); a non-`multiSelect: true` block with more than one
recommended option is a finding.

Narrative-marker leak. The `(Recommended)` (and the prose-and-document
`**Recommended**`) marker lives SOLELY in the option label per
`rules/interactive-questions-canonical-shapes.md` §2.1; the body carries
verifiable concrete-driver evidence instead. A marker surfacing on a body
segment line (``rationale:`` / ``recommendation:`` / ``default-pointer:``) is a
`narrative-marker-leak` finding. The label's own legitimate postfix is never a
leak — a label line carries no body-segment lead-in token.

Definitional exclusion. The rule files that *define* the option-annotation
convention quote non-canonical and deliberately-bound-violating examples as
specification material; sweeping them would flag their definitional examples.
Those files are excluded by path, mirroring the §3 exclusion zones of
`rules/interactive-questions-sweep-matchers.md`.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# Recommendation taxonomy value on a body segment, per the canonical channel §4.
_RECOMMENDATION_VALUE_RE: Final[re.Pattern[str]] = re.compile(
    r"recommendation:\s*(?P<value>recommended|acceptable|discouraged|destructive-no-default)\b"
)

# Option label shapes. Backtick form ``- `Label`:`` (command / fallback prose)
# and YAML form ``label: Label`` / ``- label: Label`` (fenced worked examples).
_BACKTICK_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*>?\s*-\s*`(?P<label>[^`]+)`\s*:"
)
_YAML_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*-?\s*label:\s*(?P<label>\S.*?)\s*$"
)
_BOLD_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*>?\s*-\s*\*\*(?P<label>[^*]+)\*\*\s*:"
)

# Canonical postfix is capital `(Recommended)`, case-correct. The lowercase
# form is the banned variant.
_CANONICAL_POSTFIX_RE: Final[re.Pattern[str]] = re.compile(r"\(Recommended\)\s*$")
_LOWERCASE_POSTFIX_RE: Final[re.Pattern[str]] = re.compile(r"\(recommended\)\s*$")

# The canonical recommended marker in either of its two surface forms: the
# structured-inquiry label postfix `(Recommended)` and the prose-and-document
# inline marker `**Recommended**`. The marker lives SOLELY in the option label
# per `rules/interactive-questions-canonical-shapes.md` §2.1; a marker surfacing
# inside a body/narrative segment is a `narrative-marker-leak`.
_BODY_MARKER_RE: Final[re.Pattern[str]] = re.compile(
    r"\(Recommended\)|\*\*Recommended\*\*"
)

# Body-segment lead-in tokens. A leak is flagged only when the marker rides on
# one of the three canonical body segments, so a stray prose line near an option
# is not mistaken for a narrative-embedded marker.
_BODY_SEGMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:rationale|recommendation|default-pointer)\s*:"
)

# Invocation-head markers used only to bound cardinality blocks. Over-
# segmentation (a prose mention of the channel) is conservative — it only
# shrinks a block, which can never manufacture a false cardinality finding.
_INVOCATION_HEAD_RE: Final[re.Pattern[str]] = re.compile(
    r"structured[- ]inquiry\s*:\s*question"
    r"|Invoke the structured-inquiry channel"
    r"|structured inquiry:"
    # Canonical YAML invocation head: a `question:` field at line start opens a
    # structured-inquiry block, so each YAML question bounds its own cardinality
    # block. This stops two independent single-select YAML option sets from
    # being read as one block, and a multiSelect:true block from masking a
    # sibling single-select block's cardinality.
    r"|^\s*question:\s*\S",
    re.IGNORECASE,
)
_MULTISELECT_TRUE_RE: Final[re.Pattern[str]] = re.compile(r"multiSelect:\s*true\b")

# Body window cap: an option's body is the lines from its label up to the next
# label line, bounded by this many lines so a runaway scan cannot bind an
# option to a distant unrelated recommendation value.
_BODY_WINDOW_LINES: Final[int] = 14

# Rule / skill files that DEFINE the option-annotation convention. Their
# worked examples are specification material, not live invocations.
_EXCLUDED_BASENAMES: Final[frozenset[str]] = frozenset(
    {
        "interactive-questions.md",
        "interactive-questions-canonical-shapes.md",
        "interactive-questions-sweep-matchers.md",
        "option-annotation.md",
        "option-annotation-form.md",
        "operational-mandates.md",
        "master-template.md",
    }
)
# Full relative-tail exclusions for files whose basename is generic.
_EXCLUDED_TAILS: Final[tuple[str, ...]] = (
    "skills/ecosystem-audit/SKILL.md",
    "skills/plan-suite/SKILL.md",
)

GREP_NAME: Final[str] = "option-annotation-grep"
RULE_ANCHOR: Final[str] = "M7 option-annotation (H6 per-option bind)"


@dataclass(frozen=True)
class Finding:
    """One per-option (or per-block) bind violation."""

    line: int
    kind: str
    label: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class _Option:
    line: int  # 1-indexed label line
    label: str
    has_canonical_postfix: bool
    has_lowercase_postfix: bool
    body_recommended: bool
    # 1-indexed line of a marker leak inside a body segment, or None.
    narrative_marker_leak_line: int | None = None


def _is_excluded(path: Path | None) -> bool:
    if path is None:
        return False
    if path.name in _EXCLUDED_BASENAMES:
        return True
    posix = path.as_posix()
    return any(posix.endswith(tail) for tail in _EXCLUDED_TAILS)


def _label_line(line: str) -> str | None:
    """Return the option label text if *line* is an option label, else None."""
    for pattern in (_BACKTICK_LABEL_RE, _BOLD_LABEL_RE, _YAML_LABEL_RE):
        m = pattern.match(line)
        if m:
            return m.group("label").strip()
    return None


def _parse_options(lines: list[str]) -> list[_Option]:
    """Extract every annotated option (a label whose body carries a value)."""
    # Pre-compute the line index of every label so a body scan can stop at the
    # next label rather than bleeding into the following option.
    label_indices = [i for i, ln in enumerate(lines) if _label_line(ln) is not None]
    label_index_set = set(label_indices)
    options: list[_Option] = []
    for i in label_indices:
        label = _label_line(lines[i])
        if label is None:  # pragma: no cover - guarded by label_indices
            continue
        window_end = min(i + 1 + _BODY_WINDOW_LINES, len(lines))
        body_value: str | None = None
        leak_line: int | None = None
        for j in range(i + 1, window_end):
            if j in label_index_set:
                break  # body ends at the next option label
            if body_value is None:
                value_match = _RECOMMENDATION_VALUE_RE.search(lines[j])
                if value_match:
                    body_value = value_match.group("value")
            # Marker-leak detection runs across the WHOLE body window, not just
            # up to the recommendation value, so a marker riding a later
            # `default-pointer:` segment is caught too. A leak is a marker on a
            # canonical body segment line.
            if (
                leak_line is None
                and _BODY_SEGMENT_RE.search(lines[j])
                and _BODY_MARKER_RE.search(lines[j])
            ):
                leak_line = j + 1
        if body_value is None:
            # No recommendation value in this label's body: not an annotated
            # option subject to the bind (e.g., a prose list item). Skip.
            continue
        options.append(
            _Option(
                line=i + 1,
                label=label,
                has_canonical_postfix=_CANONICAL_POSTFIX_RE.search(label) is not None,
                has_lowercase_postfix=_LOWERCASE_POSTFIX_RE.search(label) is not None,
                body_recommended=body_value == "recommended",
                narrative_marker_leak_line=leak_line,
            )
        )
    return options


def _block_of(line_idx: int, head_indices: list[int]) -> int:
    """Return the index of the nearest preceding invocation head (or -1)."""
    block = -1
    for k, head in enumerate(head_indices):
        if head <= line_idx:
            block = k
        else:
            break
    return block


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan *content* for per-option Recommended-bind violations.

    Pre-conditions: *content* is the artifact body about to be emitted; *path*
    is its destination (used only for definitional-file exclusion).
    Post-conditions: ``result.passed`` is True when every annotated option
    satisfies the bidirectional bind (capital canonical postfix iff body value
    is ``recommended``), no label carries the lowercase variant, and no
    single-select block recommends more than one option.
    """
    if _is_excluded(path):
        return GrepResult(grep=GREP_NAME, path=_path_str(path), passed=True)

    lines = content.splitlines()
    options = _parse_options(lines)
    findings: list[Finding] = []

    for opt in options:
        if opt.has_lowercase_postfix:
            findings.append(
                Finding(
                    line=opt.line,
                    kind="non-canonical-postfix-case",
                    label=opt.label,
                    detail="label uses lowercase (recommended); canonical form is (Recommended)",
                )
            )
        if (
            opt.body_recommended
            and not opt.has_canonical_postfix
            and not opt.has_lowercase_postfix
        ):
            findings.append(
                Finding(
                    line=opt.line,
                    kind="missing-canonical-postfix",
                    label=opt.label,
                    detail="body recommendation: recommended but label lacks the (Recommended) postfix",
                )
            )
        if opt.has_canonical_postfix and not opt.body_recommended:
            findings.append(
                Finding(
                    line=opt.line,
                    kind="spurious-postfix",
                    label=opt.label,
                    detail="label carries (Recommended) but body recommendation is not recommended",
                )
            )
        if opt.narrative_marker_leak_line is not None:
            findings.append(
                Finding(
                    line=opt.narrative_marker_leak_line,
                    kind="narrative-marker-leak",
                    label=opt.label,
                    detail=(
                        "the (Recommended) / **Recommended** marker appears in a "
                        "body segment (rationale:/recommendation:/default-pointer:); "
                        "it lives solely in the option label"
                    ),
                )
            )

    # Cardinality: per invocation block, a non-multiSelect-true question carries
    # at most one recommended option.
    head_indices = [i for i, ln in enumerate(lines) if _INVOCATION_HEAD_RE.search(ln)]
    multiselect_blocks: set[int] = set()
    if head_indices:
        for i, ln in enumerate(lines):
            if _MULTISELECT_TRUE_RE.search(ln):
                multiselect_blocks.add(_block_of(i, head_indices))
    else:
        # No invocation head: treat the whole file as one implicit block.
        if any(_MULTISELECT_TRUE_RE.search(ln) for ln in lines):
            multiselect_blocks.add(0)
    block_recommended: dict[int, list[_Option]] = {}
    for opt in options:
        if not opt.body_recommended:
            continue
        block = _block_of(opt.line - 1, head_indices) if head_indices else 0
        block_recommended.setdefault(block, []).append(opt)
    for block, recs in block_recommended.items():
        if block in multiselect_blocks:
            continue
        if len(recs) > 1:
            findings.append(
                Finding(
                    line=recs[1].line,
                    kind="single-select-multi-recommended",
                    label=recs[1].label,
                    detail=(
                        f"single-select block recommends {len(recs)} options; "
                        "at most one is permitted"
                    ),
                )
            )

    findings.sort(key=lambda f: (f.line, f.kind))
    return GrepResult(
        grep=GREP_NAME,
        path=_path_str(path),
        passed=not findings,
        findings=findings,
    )


def _path_str(path: Path | None) -> str | None:
    return str(path) if path is not None else None


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
