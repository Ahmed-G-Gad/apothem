# SPDX-License-Identifier: MIT

"""Self-tests for the completion-claim-grep validator (spec §4.2 honesty)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "completion_claim_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("completion_claim_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["completion_claim_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()
_COHORT_PATH: Final[Path] = Path("commands/sample.md")


def _kinds(result: object) -> set[str]:
    return {f.kind for f in result.findings}  # type: ignore[attr-defined]


def test_clean_prose_passes() -> None:
    body = "Run the gate; the phase is complete only when every verification passes."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed
    assert result.findings == []


def test_evidence_gated_completion_passes() -> None:
    body = "\n".join(
        [
            "The suite is not complete until zero open findings remain.",
            "Declare the pipeline complete once the suite is verified HEALTHY.",
            "NEVER mark complete without all verifications passing.",
        ]
    )
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, [f.text for f in result.findings]


def test_guaranteed_outcome_is_flagged() -> None:
    result = _MOD.check("This step is guaranteed to pass.", _COHORT_PATH)
    assert not result.passed
    assert "guaranteed-outcome" in _kinds(result)


def test_absolute_percentage_is_flagged() -> None:
    result = _MOD.check("The output is 100% complete after this.", _COHORT_PATH)
    assert not result.passed
    assert "absolute-percentage" in _kinds(result)


def test_cannot_fail_is_flagged() -> None:
    result = _MOD.check("The migration cannot fail.", _COHORT_PATH)
    assert not result.passed
    assert "cannot-fail" in _kinds(result)


def test_always_succeeds_and_never_fails_are_flagged() -> None:
    result = _MOD.check(
        "The build always works and the test never fails.", _COHORT_PATH
    )
    assert not result.passed
    assert "always-succeeds" in _kinds(result)
    assert "never-fails" in _kinds(result)


def test_finding_records_line_number() -> None:
    body = "line one is fine\nthis is guaranteed to succeed\nline three is fine"
    result = _MOD.check(body, _COHORT_PATH)
    assert not result.passed
    assert any(f.line == 2 for f in result.findings)


def test_non_cohort_md_path_is_out_of_scope() -> None:
    # A .md outside the cohort directories is not directive/output prose.
    result = _MOD.check("guaranteed to pass", Path("docs/notes.md"))
    assert result.passed


def test_code_path_is_out_of_scope() -> None:
    result = _MOD.check("guaranteed to pass", Path("commands/helper.py"))
    assert result.passed


def test_grep_own_module_basename_is_excluded() -> None:
    # The grep's own definitional file quotes the phrases as examples. It is a
    # `.py` file, so `_in_scope` rejects it on the suffix check before the
    # basename exclusion — the exclusion set is `.md`-scoped (see below).
    result = _MOD.check(
        "guaranteed to pass", Path("src/apothem/conformity/completion_claim_grep.py")
    )
    assert result.passed


def test_discipline_rule_md_is_excluded() -> None:
    # session-closure.md is the rule that anchors this matcher and quotes the
    # banned phrases as anti-pattern examples; excluded so the definition is
    # not itself a finding. This is the `.md`-relevant exclusion that replaced
    # the never-firing `.py` basename entry.
    assert "session-closure.md" in _MOD._EXCLUDED_BASENAMES
    result = _MOD.check("guaranteed to pass", Path("rules/session-closure.md"))
    assert result.passed


def test_other_rules_md_is_still_scanned() -> None:
    # A different rules/*.md is directive prose and is still checked.
    result = _MOD.check("This step is guaranteed to pass.", Path("rules/other-rule.md"))
    assert not result.passed
    assert "guaranteed-outcome" in _kinds(result)


def test_fenced_phrase_is_excluded() -> None:
    # A banned phrase quoted inside a fenced code block is example material,
    # not the artifact's own directive prose, so it is not flagged.
    body = "\n".join(
        [
            "The phase completes when every verification passes.",
            "```text",
            "guaranteed to pass",
            "cannot fail",
            "```",
            "Run the gate to confirm.",
        ]
    )
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, [f.text for f in result.findings]


def test_phrase_outside_fence_still_flagged_with_fence_present() -> None:
    # Prose outside the fence is still scanned even when a fenced block exists.
    body = "\n".join(
        [
            "```text",
            "sample output",
            "```",
            "This step is guaranteed to pass.",
        ]
    )
    result = _MOD.check(body, _COHORT_PATH)
    assert not result.passed
    assert "guaranteed-outcome" in _kinds(result)
