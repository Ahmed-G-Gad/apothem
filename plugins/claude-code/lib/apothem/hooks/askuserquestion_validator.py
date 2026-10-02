# SPDX-License-Identifier: MIT

"""Call-time validator for the ``AskUserQuestion`` tool's option payload.

Why this validator exists. The option-annotation matchers
(``conformity/option_annotation_grep.py``) scan committed ``*.md`` artifacts —
they verify the canonical ``(Recommended)`` marker on rendered option sets that
already live in the tree. Nothing inspected the LIVE ``AskUserQuestion`` tool
payload at the moment the agent asks the operator, so a malformed or absent
marker reached the operator unchecked. This module is the dispatch-routed
``PreToolUse`` handler that closes that gap: it receives the tool input (a
``questions`` array, each question carrying ``options[].label`` and
``multiSelect``), validates marker well-formedness against the canonical rule,
and emits advisory ``additionalContext`` (default) or, under the repo's strict
opt-in, a ``permissionDecision: deny`` envelope.

What it CAN guarantee. Well-formedness: a marker present on a label is in the
canonical form (capital ``(Recommended)``, exact end-of-label placement, one
leading space, not on a destructive option, at most one per single-select
question). These are objectively decidable from the payload alone.

What it CANNOT guarantee. The native ``AskUserQuestion`` payload carries no
separate "recommended" field — the marker IS the only signal of which option is
recommended. So this validator cannot prove a missing marker is a defect: a
single-select question with two substantive options and zero markers is merely
*advised* (a NUDGE) to mark its recommended option, never blocked. Forcing a
recommendation to exist is a behavioral-convention obligation the rules carry,
not a fact this runtime check can decide.

Contract. Fast (sub-second; pure-Python regex over a small payload),
idempotent, and FAIL-OPEN: any exception → allow the call (an empty envelope),
never crash the operator's question. The strict opt-in mirrors the conformity
gate's: the ``--strict`` flag or a truthy ``APOTHEM_CONFORMITY_STRICT``
environment variable escalates WELL-FORMEDNESS findings (never the NUDGE) to a
``permissionDecision: deny``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Final, Literal

# Strict opt-in mirrors the conformity gate's (``conformity/gate.py``). Reused
# verbatim here so the AskUserQuestion validator and the per-Write gate share
# one strict-mode contract: the operator enables blocking once, for both.
STRICT_ENV: Final[str] = "APOTHEM_CONFORMITY_STRICT"
_STRICT_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})

# Canonical recommended-marker forms, kept in lockstep with the static matcher
# at ``conformity/option_annotation_grep.py``. The canonical postfix is capital
# ``(Recommended)`` at the exact end of the label with one leading space; the
# lowercase ``(recommended)`` form is a banned variant. We re-derive the same
# anchored patterns here because the static matcher operates on Markdown lines
# (``- `Label`:``) while this validator operates on a structured label string,
# so the line-shaped label regexes there do not apply — but the postfix rules
# (case, bracket, end-anchor) are identical and MUST NOT diverge.
_CANONICAL_POSTFIX_RE: Final[re.Pattern[str]] = re.compile(r" \(Recommended\)$")
_LOWERCASE_POSTFIX_RE: Final[re.Pattern[str]] = re.compile(r"\(recommended\)\s*$")
# Any non-canonical bracketing / spacing of the recommended token at the label
# tail: ``[Recommended]``, ``(Rec)``, ``(Recommended )``, ``( Recommended )`` —
# anything that names "recommend" near the tail but is not the exact canonical
# ``" (Recommended)"`` postfix.
_NONCANONICAL_TAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"[\[(]\s*rec(?:ommend(?:ed)?)?\s*[\])]\s*$", re.IGNORECASE
)

# Destructive-intent label tokens. A recommended marker on a clearly-destructive
# option contradicts the no-default floor for irreversible operations
# (``rules/interactive-questions-canonical-shapes.md`` §5.8): a recommendation
# marker on an irreversible action steers the operator toward the dangerous path.
_DESTRUCTIVE_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b("
    r"delete|remove|retire|discard|destroy|wipe|erase|drop|purge|"
    r"overwrite|reset|revert|rm|truncate|force[- ]?push"
    r")\b",
    re.IGNORECASE,
)

# A "substantive" option for the NUDGE heuristic: anything that is not the
# harness-implicit free-text escape hatch (the ``Other`` option the tool adds).
_IMPLICIT_OTHER_RE: Final[re.Pattern[str]] = re.compile(r"^\s*other\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    """One validation result against the canonical marker rules.

    ``severity`` is ``"finding"`` for an objectively-decidable well-formedness
    violation (escalatable to a block under strict mode) or ``"nudge"`` for the
    heuristic missing-marker advisory (never escalated — it can only advise).
    The ``Literal`` pins the two-value domain so a typo (``"warn"``) is a
    type error rather than a silently-mis-severitied finding.
    """

    severity: Literal["finding", "nudge"]
    kind: str
    question_index: int
    label: str
    detail: str


@dataclass(frozen=True)
class ValidationResult:
    """Aggregate outcome of validating one ``AskUserQuestion`` payload."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def wellformedness_findings(self) -> list[Finding]:
        """Objectively-decidable violations (block-eligible under strict mode)."""
        return [f for f in self.findings if f.severity == "finding"]

    @property
    def nudges(self) -> list[Finding]:
        """Heuristic missing-marker advisories (never block)."""
        return [f for f in self.findings if f.severity == "nudge"]


def strict_enabled(argv: list[str] | None = None) -> bool:
    """Return True when the strict opt-in is active.

    Mirrors ``conformity/gate.py``: the ``--strict`` flag or a truthy
    ``APOTHEM_CONFORMITY_STRICT`` environment variable enables blocking.
    """
    args = argv if argv is not None else sys.argv[1:]
    if "--strict" in args:
        return True
    return os.environ.get(STRICT_ENV, "").strip().lower() in _STRICT_TRUTHY


def _label_is_canonical_marked(label: str) -> bool:
    """True iff the label ends with the exact canonical ``" (Recommended)"``."""
    return _CANONICAL_POSTFIX_RE.search(label) is not None


def _label_has_lowercase_marker(label: str) -> bool:
    """True iff the label ends with the banned lowercase ``(recommended)``."""
    return _LOWERCASE_POSTFIX_RE.search(label) is not None


def _label_has_noncanonical_marker(label: str) -> bool:
    """True iff the label tail names a recommended token in a non-canonical form.

    Catches ``[Recommended]``, ``(Rec)``, ``(Recommended )``, ``( Recommended )``
    and similar bracketed tail variants. The canonical ``" (Recommended)"`` form
    is excluded (it is the legitimate postfix); the lowercase variant is reported
    separately as ``non-canonical-postfix-case`` so its detail is precise.
    """
    if _label_is_canonical_marked(label):
        return False
    if _label_has_lowercase_marker(label):
        return False
    return _NONCANONICAL_TAIL_RE.search(label) is not None


def _is_destructive_label(label: str) -> bool:
    """True iff the label names a clearly-destructive / irreversible action."""
    return _DESTRUCTIVE_LABEL_RE.search(label) is not None


def _is_substantive_option(label: str) -> bool:
    """True iff the option is a real choice, not the implicit ``Other`` escape."""
    return bool(label.strip()) and _IMPLICIT_OTHER_RE.match(label) is None


def _option_labels(question: dict[str, object]) -> list[str]:
    """Extract the option labels from one question, tolerating shape drift."""
    raw_options = question.get("options")
    if not isinstance(raw_options, list):
        return []
    labels: list[str] = []
    for option in raw_options:
        if isinstance(option, str):
            labels.append(option)
        elif isinstance(option, dict):
            label = option.get("label")
            if isinstance(label, str):
                labels.append(label)
    return labels


def _validate_question(index: int, question: dict[str, object]) -> list[Finding]:
    """Validate one question's option labels against the canonical marker rules."""
    findings: list[Finding] = []
    labels = _option_labels(question)
    if not labels:
        return findings
    multi_select = bool(question.get("multiSelect", False))

    canonical_marked = 0
    for label in labels:
        if _label_has_lowercase_marker(label):
            findings.append(
                Finding(
                    severity="finding",
                    kind="non-canonical-postfix-case",
                    question_index=index,
                    label=label,
                    detail=(
                        "label uses lowercase (recommended); the canonical form "
                        "is the capital (Recommended) postfix"
                    ),
                )
            )
        elif _label_has_noncanonical_marker(label):
            findings.append(
                Finding(
                    severity="finding",
                    kind="non-canonical-postfix-form",
                    question_index=index,
                    label=label,
                    detail=(
                        "label names a recommended token in a non-canonical "
                        "bracket/spacing form; the canonical form is the exact "
                        '" (Recommended)" postfix with one leading space at the '
                        "end of the label"
                    ),
                )
            )
        elif _label_is_canonical_marked(label):
            canonical_marked += 1
            if _is_destructive_label(label):
                findings.append(
                    Finding(
                        severity="finding",
                        kind="recommended-on-destructive",
                        question_index=index,
                        label=label,
                        detail=(
                            "the (Recommended) marker rides a clearly-destructive "
                            "option; an irreversible action must not be the "
                            "recommended (and easy) path"
                        ),
                    )
                )

    if not multi_select and canonical_marked > 1:
        findings.append(
            Finding(
                severity="finding",
                kind="single-select-multi-recommended",
                question_index=index,
                label="",
                detail=(
                    f"single-select question carries {canonical_marked} "
                    "(Recommended) markers; at most one is permitted "
                    "(set multiSelect: true to recommend several)"
                ),
            )
        )

    # NUDGE: a single-select question with two or more substantive options and
    # zero markers. Heuristic only — the native payload carries no separate
    # "recommended" field, so a missing marker cannot be proven a defect.
    substantive = [lab for lab in labels if _is_substantive_option(lab)]
    if not multi_select and len(substantive) >= 2 and canonical_marked == 0:
        findings.append(
            Finding(
                severity="nudge",
                kind="no-recommended-marker",
                question_index=index,
                label="",
                detail=(
                    f"single-select question offers {len(substantive)} "
                    "substantive options but marks none (Recommended); the "
                    "option-annotation discipline advises marking the "
                    "recommended option so the operator sees the agent's "
                    "evaluation"
                ),
            )
        )
    return findings


def validate_payload(payload: dict[str, object] | None) -> ValidationResult:
    """Validate an ``AskUserQuestion`` tool payload's option markers.

    Pre-condition: *payload* is the harness ``PreToolUse`` stdin object (or
    ``None`` when stdin carried no parseable object). Post-condition: every
    well-formedness violation and missing-marker nudge across every question is
    enumerated; an unparseable or shapeless payload yields an empty result
    (fail-open — nothing to validate).
    """
    if not payload:
        return ValidationResult()
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ValidationResult()
    questions = tool_input.get("questions")
    if not isinstance(questions, list):
        return ValidationResult()
    findings: list[Finding] = []
    for index, question in enumerate(questions):
        if isinstance(question, dict):
            findings.extend(_validate_question(index, question))
    return ValidationResult(findings=findings)


def _read_payload() -> dict[str, object] | None:
    """Read and parse the hook's stdin JSON payload, fail-open on any error."""
    try:
        if sys.stdin.isatty():
            return None
        raw = sys.stdin.read()
    except (OSError, ValueError):
        # ValueError covers a read from an already-closed stdin. Matches
        # lib/stdin_json.read_stdin_json; catching only OSError let that case
        # crash a hook whose whole contract is to fail open.
        return None
    if not raw or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _format_findings(findings: list[Finding]) -> str:
    """Render findings as one human-readable line each."""
    lines: list[str] = []
    for finding in findings:
        label = f" label={finding.label!r}" if finding.label else ""
        lines.append(
            f"  - [Q{finding.question_index}] {finding.kind}{label}: {finding.detail}"
        )
    return "\n".join(lines)


def build_envelope(result: ValidationResult, *, strict: bool) -> dict[str, object]:
    """Map a validation result to a hook-output envelope.

    Default (advisory): ``additionalContext`` surfacing well-formedness findings
    and nudges to the model, which is the party that can fix the labels; the
    question proceeds. Strict: ``permissionDecision: deny`` with the findings as
    ``permissionDecisionReason`` when well-formedness findings exist (nudges
    never block). Both live in ``hookSpecificOutput``, the PreToolUse channel;
    the top-level ``decision`` field is deprecated for PreToolUse and a
    ``systemMessage`` reaches only the operator. A clean result yields an empty
    envelope (the question proceeds silently).
    """
    wellformedness = result.wellformedness_findings
    nudges = result.nudges
    if strict and wellformedness:
        reason_lines = [
            "Apothem AskUserQuestion guard (strict): the option set carries "
            "(Recommended)-marker well-formedness violation(s). Fix the "
            "label(s) and re-ask:",
            _format_findings(wellformedness),
        ]
        if nudges:
            reason_lines.append("Advisory (not blocking):\n" + _format_findings(nudges))
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "\n".join(reason_lines),
            }
        }

    advisory: list[Finding] = [*wellformedness, *nudges]
    if not advisory:
        return {}
    header = (
        "Apothem AskUserQuestion guard (advisory): review the "
        "(Recommended)-marker finding(s) below; the question proceeds. "
        "Set APOTHEM_CONFORMITY_STRICT=1 (or pass --strict) to block on "
        "well-formedness violations."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": header + "\n" + _format_findings(advisory),
        }
    }


def main(argv: list[str] | None = None) -> None:
    """Entry point. Validates the payload and emits one envelope; never raises.

    FAIL-OPEN: any unexpected exception is swallowed and an empty (allow)
    envelope is written, so a validator bug never crashes the operator's
    question.
    """
    try:
        strict = strict_enabled(argv)
        payload = _read_payload()
        result = validate_payload(payload)
        envelope = build_envelope(result, strict=strict)
        sys.stdout.write(json.dumps(envelope, separators=(",", ":")) + "\n")
    except Exception:  # noqa: BLE001, RUF100 - fail-open boundary: a validator error must never block the operator's question; emit an allow envelope and proceed (BLE001 is the intent marker; RUF100 self-suppresses because ruff's BLE family is not active)
        sys.stdout.write("{}\n")


if __name__ == "__main__":
    main()
