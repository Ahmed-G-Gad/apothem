# SPDX-License-Identifier: MIT

"""Self-tests for the hedging-grep validator (inline-code citation carve-out).

Regression focus: a hedge word quoted inside a single-backtick inline-code
span is a meta-linguistic citation — a doc naming the vocabulary it forbids —
not a prescription that hedges. The matcher blanks inline-code spans before
the scan so the citation passes, while a bare hedge in prose still fires and a
hedge inside a fenced block stays excluded. Before this carve-out, any doc
that documented the closed hedging vocabulary inside backticks tripped the
matcher on its own citation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "hedging_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hedging_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["hedging_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()
_COHORT_PATH: Final[Path] = Path("rules/sample.md")


def _matches(result: object) -> list[str]:
    return [f.match for f in result.findings]  # type: ignore[attr-defined]


# --- backtick-cited hedge is excluded (the regression) ----------------------


def test_backtick_cited_hedge_passes() -> None:
    body = "The closed hedging list names `usually`, `typically`, and `maybe`."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


def test_backtick_cited_hedge_in_forbidden_sentence_passes() -> None:
    body = "A prescription using `usually` is forbidden where a binding form fits."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


def test_backtick_cited_multiword_hedge_passes() -> None:
    body = "The phrase `should probably` is a hedge and must not appear bare."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


# --- bare hedge in prose is still flagged (true positives kept) -------------


def test_bare_hedge_still_flagged() -> None:
    result = _MOD.check(
        "The build usually completes within five minutes.", _COHORT_PATH
    )
    assert not result.passed
    assert "usually" in _matches(result)


def test_bare_multiword_hedge_still_flagged() -> None:
    result = _MOD.check("Users should probably tune the cache.", _COHORT_PATH)
    assert not result.passed
    assert "should probably" in [m.lower() for m in _matches(result)]


def test_mixed_line_bare_flagged_cited_excluded() -> None:
    # The bare "usually" (before "completes") fires; the backtick-cited
    # `typically` is blanked — column preservation keeps them independent.
    body = "The build usually completes, though `typically` is itself a hedge word."
    result = _MOD.check(body, _COHORT_PATH)
    assert not result.passed
    matches = [m.lower() for m in _matches(result)]
    assert matches.count("usually") == 1
    assert "typically" not in matches


# --- fenced-block exclusion is preserved ------------------------------------


def test_fenced_block_hedge_still_excluded() -> None:
    body = "\n".join(["```text", "This usually works inside a fence.", "```"])
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


# --- the hedging filler AGENTS.md and CLAUDE.md forbid -----------------------


def test_forbidden_filler_phrases_fail() -> None:
    """``basically``, ``kind of`` and ``in some sense`` hedge a directive."""
    body = (
        "You should basically run the tests. It is kind of required.\n"
        "In some sense the cache is optional."
    )
    result = _MOD.check(body, _COHORT_PATH)
    assert not result.passed
    assert sorted(m.lower() for m in _matches(result)) == [
        "basically",
        "in some sense",
        "kind of",
    ]


def test_filler_quoted_in_backticks_passes() -> None:
    """The rule text that names the filler cites it, it does not hedge."""
    body = "Hedging filler such as `basically`, `kind of`, and `in some sense` is forbidden."
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)


def test_kind_of_as_a_noun_phrase_passes() -> None:
    """``what kind of`` / ``this kind of`` name a category; they do not hedge."""
    body = (
        "What kind of project is this? This kind of change needs a test.\n"
        "A kind of index, the kind of input, any kind of file, two kinds of output."
    )
    result = _MOD.check(body, _COHORT_PATH)
    assert result.passed, _matches(result)
