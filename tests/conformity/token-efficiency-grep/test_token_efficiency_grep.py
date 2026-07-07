# SPDX-License-Identifier: MIT

"""Self-tests for the token-efficiency-grep validator (qualifier carve-out).

Regression focus: the bare word "rather" is a content-free qualifier as an
intensifier ("rather slow") but carries semantic load in the comparative
construction "rather than" ("X rather than Y"). The matcher must flag the
former and pass the latter — earlier it flagged both, producing false
positives on legitimate comparative prose across the shipped command and
rule corpus.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "token_efficiency_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("token_efficiency_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["token_efficiency_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()
_COHORT_PATH: Final[Path] = Path("commands/sample.md")


def _matches(result: object) -> list[str]:
    return [f.match for f in result.findings]  # type: ignore[attr-defined]


# --- "rather than" comparative form passes (the regression) -----------------


def test_rather_than_comparative_passes() -> None:
    body = "Repair the dead link in place rather than deferring it to a follow-up."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


def test_rather_than_capitalized_passes() -> None:
    body = "Rather than rewrite the module, extend it in place."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


def test_rather_than_extra_whitespace_passes() -> None:
    body = "Prefer the measured form rather  than the bare intensifier."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


def test_multiple_rather_than_clauses_pass() -> None:
    body = (
        "Narrate the product rather than its history, and reference the current "
        "release rather than the superseded one."
    )
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


# --- bare-intensifier "rather" is still flagged (true positives kept) -------


def test_rather_slow_intensifier_is_flagged() -> None:
    result = _MOD.check("The cold-start path is rather slow.", _COHORT_PATH)
    assert not result.passed
    assert "rather" in _matches(result)


def test_rather_large_intensifier_is_flagged() -> None:
    result = _MOD.check("The generated payload is rather large.", _COHORT_PATH)
    assert not result.passed
    assert "rather" in _matches(result)


def test_rather_at_end_of_line_is_flagged() -> None:
    # A dangling intensifier with no comparative "than" following.
    result = _MOD.check("The approach feels rather", _COHORT_PATH)
    assert not result.passed
    assert "rather" in _matches(result)


def test_rather_comma_than_is_flagged() -> None:
    # "rather, than" is not the comparative construction; the lookahead
    # requires whitespace immediately before "than", so this still flags.
    result = _MOD.check("It is rather, than not, the safer path.", _COHORT_PATH)
    assert not result.passed
    assert "rather" in _matches(result)


# --- the other qualifiers are untouched by the carve-out --------------------


def test_other_qualifiers_still_flagged() -> None:
    result = _MOD.check(
        "It is very fast, quite small, somewhat odd, and fairly stable.",
        _COHORT_PATH,
    )
    assert not result.passed
    matches = {m.lower() for m in _matches(result)}
    assert {"very", "quite", "somewhat", "fairly"} <= matches


def test_filler_phrase_still_flagged() -> None:
    result = _MOD.check("In this section, we will cover the gate.", _COHORT_PATH)
    assert not result.passed


# --- mixed line: comparative excluded, intensifier kept ---------------------


def test_comparative_and_intensifier_on_one_line() -> None:
    body = "Prefer X rather than Y, though Y is rather slow and very large."
    result = _MOD.check(body, _COHORT_PATH)
    assert not result.passed
    matches = _matches(result)
    # The comparative "rather than" contributes no finding; the bare
    # intensifier "rather" (before "slow") and "very" each contribute one.
    assert matches.count("rather") == 1
    assert "very" in matches


# --- clean comparative prose contributes zero findings ----------------------


def test_clean_comparative_prose_passes() -> None:
    body = "\n".join(
        [
            "Address the root cause rather than the symptom.",
            "Surface the gap rather than entrench it.",
        ]
    )
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)
    assert result.findings == []


# --- inline-code citation carve-out -----------------------------------------
# A filler phrase or qualifier quoted inside a single-backtick inline-code span
# is a meta-linguistic citation (a doc naming the vocabulary it forbids), not
# prose that uses it. The matcher blanks inline-code spans before the scan, so
# the citation passes while a bare occurrence still fires.


def test_backtick_cited_filler_phrase_passes() -> None:
    # The exact shape that tripped the matcher on AGENTS.md / CLAUDE.md: the
    # forbidden phrase is named inside backticks within a "forbidden" sentence.
    body = "Hedging filler such as `basically`, `kind of`, and `in some sense` is forbidden."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


def test_bare_filler_phrase_still_flagged() -> None:
    result = _MOD.check("This change is kind of risky.", _COHORT_PATH)
    assert not result.passed
    assert "kind of" in _matches(result)


def test_backtick_cited_qualifier_passes() -> None:
    body = "The qualifier `very` is content-free and forbidden in prescriptive prose."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


def test_mixed_line_bare_qualifier_flagged_cited_excluded() -> None:
    # The bare "very" (before "fast") fires; the backtick-cited `very` is
    # blanked — column preservation keeps the two occurrences independent.
    body = "The scheduler is very fast, though the `very` token alone is a citation."
    result = _MOD.check(body, _COHORT_PATH)
    assert not result.passed
    assert _matches(result).count("very") == 1
