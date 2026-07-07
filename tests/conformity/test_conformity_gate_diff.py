# SPDX-License-Identifier: MIT

"""Behavior contract for the conformity-gate differential-gating layer.

Tests cover the deferred matcher fix at the orchestrator: pre-existing
findings on a codebase file must NOT block Edits whose scope does not
touch the offending line. The differential layer canonicalises every
finding by stripping position-only keys (line / column / occurrences /
context) and suppresses any post-edit finding whose signature matches a
pre-edit finding. Only newly-introduced findings remain.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Final

import pytest

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "conformity"
_MODULE_PATH = _TOOLS_DIR / "gate.py"

# Symbolic test-data constants. Named to communicate intent in the
# AAA-shape tests below and to satisfy the magic-number discipline at
# M13.10 (UPPER_SNAKE assignment lines are recognized as named-constant
# declarations and exempt from the numeric-literal sweep).
FINDING_VALUE_PRE: Final[str] = "alpha"
FINDING_VALUE_POST: Final[str] = "beta"
PRE_LINE: Final[int] = 12
SHIFTED_LINE: Final[int] = 13
OTHER_LINE: Final[int] = 30
COLUMN_PRE: Final[int] = 4
COLUMN_POST: Final[int] = 1
RULE_ANCHOR: Final[str] = "M13.10"
GREP_MN: Final[str] = "magic-number-grep"
GREP_UA: Final[str] = "unpinned-action-grep"
ELAPSED_SECONDS: Final[float] = 0.001


def _load_module():
    """Load the hyphen-named orchestrator module via importlib spec."""
    spec = importlib.util.spec_from_file_location("conformity_gate", _MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module spec from {_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["conformity_gate"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    """Return the loaded conformity-gate orchestrator module."""
    return _load_module()


def _make_invocation(gate_module, grep: str, findings: list[dict]):
    """Construct a GrepInvocation with the given findings list."""
    return gate_module.GrepInvocation(
        grep=grep,
        passed=not findings,
        findings=findings,
        elapsed_seconds=ELAPSED_SECONDS,
        over_budget=False,
    )


def _finding(value: str, line: int, column: int | None = None) -> dict:
    """Build a finding dict honoring the canonical schema."""
    record: dict = {"value": value, "line": line, "rule": RULE_ANCHOR}
    if column is not None:
        record["column"] = column
    return record


def test_position_keys_set_covers_canonical_position_fields(gate) -> None:
    """`_POSITION_KEYS` must enumerate every per-finding position field."""
    expected = {
        "line",
        "lineno",
        "line_number",
        "start_line",
        "end_line",
        "column",
        "col",
        "pos",
        "position",
        "range",
        "occurrences",
        "context",
    }
    assert expected.issubset(gate._POSITION_KEYS)


def test_finding_signature_ignores_position_only_keys(gate) -> None:
    """Two findings differing ONLY in position produce identical signatures."""
    finding_a = _finding(FINDING_VALUE_PRE, PRE_LINE, COLUMN_PRE)
    finding_b = _finding(FINDING_VALUE_PRE, OTHER_LINE, COLUMN_POST)

    assert gate._finding_signature(finding_a) == gate._finding_signature(finding_b)


def test_finding_signature_distinguishes_substantive_difference(gate) -> None:
    """Two findings with different `value` must produce DIFFERENT signatures."""
    finding_a = _finding(FINDING_VALUE_PRE, PRE_LINE)
    finding_b = _finding(FINDING_VALUE_POST, PRE_LINE)

    assert gate._finding_signature(finding_a) != gate._finding_signature(finding_b)


def test_diff_invocations_suppresses_pre_existing_finding(gate) -> None:
    """A finding present in both pre and post invocations is suppressed.

    Contract from the deferred matcher fix: an Edit whose scope does not
    touch the offending line must not be blocked by the orchestrator
    re-detecting the pre-existing violation in the post-edit body.
    """
    pre_finding = _finding(FINDING_VALUE_PRE, PRE_LINE)
    post_finding = _finding(FINDING_VALUE_PRE, PRE_LINE)

    pre = [_make_invocation(gate, GREP_MN, [pre_finding])]
    post = [_make_invocation(gate, GREP_MN, [post_finding])]

    diffed = gate._diff_invocations(pre, post)

    assert len(diffed) == 1
    assert diffed[0].passed is True
    assert diffed[0].findings == []


def test_diff_invocations_retains_newly_introduced_finding(gate) -> None:
    """A finding absent pre but present post is retained (Edit introduced it)."""
    post_finding = _finding(FINDING_VALUE_POST, OTHER_LINE)

    pre = [_make_invocation(gate, GREP_MN, [])]
    post = [_make_invocation(gate, GREP_MN, [post_finding])]

    diffed = gate._diff_invocations(pre, post)

    assert len(diffed) == 1
    assert diffed[0].passed is False
    assert len(diffed[0].findings) == 1


def test_diff_invocations_handles_line_shift_as_same_finding(gate) -> None:
    """A pre-existing finding that shifts line number after Edit is suppressed.

    The deferred-fix symptom: an Edit inserting an unrelated line earlier
    in the file shifted every subsequent line-number; the orchestrator
    treated the shifted finding as fresh. Signature canonicalisation
    strips `line` so identical-value findings on identical rules match.
    """
    pre_finding = _finding(FINDING_VALUE_PRE, PRE_LINE)
    post_finding = _finding(FINDING_VALUE_PRE, SHIFTED_LINE)

    pre = [_make_invocation(gate, GREP_MN, [pre_finding])]
    post = [_make_invocation(gate, GREP_MN, [post_finding])]

    diffed = gate._diff_invocations(pre, post)

    assert diffed[0].passed is True
    assert diffed[0].findings == []


def test_diff_invocations_separates_pre_and_new_when_both_present(gate) -> None:
    """A post invocation with one pre-existing + one new finding retains only the new."""
    pre_finding = _finding(FINDING_VALUE_PRE, PRE_LINE)
    same_post = _finding(FINDING_VALUE_PRE, PRE_LINE)
    new_post = _finding(FINDING_VALUE_POST, OTHER_LINE)

    pre = [_make_invocation(gate, GREP_MN, [pre_finding])]
    post = [_make_invocation(gate, GREP_MN, [same_post, new_post])]

    diffed = gate._diff_invocations(pre, post)

    assert len(diffed) == 1
    assert diffed[0].passed is False
    assert len(diffed[0].findings) == 1
    assert diffed[0].findings[0]["value"] == FINDING_VALUE_POST


def test_diff_invocations_keys_by_matcher_grep_name(gate) -> None:
    """Findings from different matchers do not cross-cancel."""
    pre_finding = _finding(FINDING_VALUE_PRE, PRE_LINE)
    other_matcher_finding = {
        "action": "actions/checkout",
        "ref": "v4",
        "line": OTHER_LINE,
    }

    pre = [_make_invocation(gate, GREP_MN, [pre_finding])]
    post = [
        _make_invocation(gate, GREP_MN, [pre_finding]),
        _make_invocation(gate, GREP_UA, [other_matcher_finding]),
    ]

    diffed = gate._diff_invocations(pre, post)

    by_grep = {inv.grep: inv for inv in diffed}
    assert by_grep[GREP_MN].passed is True
    assert by_grep[GREP_UA].passed is False
    assert len(by_grep[GREP_UA].findings) == 1


def test_diff_invocations_handles_pre_empty_post_empty(gate) -> None:
    """Empty pre and empty post produce passed=True with no findings."""
    pre = [_make_invocation(gate, GREP_MN, [])]
    post = [_make_invocation(gate, GREP_MN, [])]

    diffed = gate._diff_invocations(pre, post)

    assert diffed[0].passed is True
    assert diffed[0].findings == []


def test_diff_invocations_duplicate_pre_findings_consumed_pairwise(gate) -> None:
    """When pre has 2 copies of a signature and post has 3, only 1 retained.

    Bag semantics: each pre-occurrence consumes exactly one post-occurrence
    of the matching signature. Excess post-occurrences surface as findings.
    """
    sig_a = _finding(FINDING_VALUE_PRE, PRE_LINE)
    sig_b = _finding(FINDING_VALUE_PRE, PRE_LINE)
    sig_c = _finding(FINDING_VALUE_PRE, SHIFTED_LINE)

    pre = [_make_invocation(gate, GREP_MN, [sig_a, sig_b])]
    post = [_make_invocation(gate, GREP_MN, [sig_a, sig_b, sig_c])]

    diffed = gate._diff_invocations(pre, post)

    assert diffed[0].passed is False
    assert len(diffed[0].findings) == 1
