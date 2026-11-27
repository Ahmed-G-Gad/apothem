# SPDX-License-Identifier: MIT

"""Behavioral pass+fail coverage for the redundancy matcher.

``redundancy_grep`` is a STANDALONE_MODULES validator that the conformity
gate runs by subprocess in ``--all`` mode, but — unlike its ``check(root)``
siblings — it is argv-scoped (``check_corpus(root, threshold)`` + ``_main``)
and therefore excluded from the in-process ``check(root)`` sweep in
``tests/conformity/test_standalone_greps_inprocess.py``. Its two argv-scoped
peers each ship a dedicated behavioral test
(``conventional-commit-grep/``, ``semver-stability-grep/``); this file is the
matching coverage for the third, so the cross-file Jaccard duplication
discrimination — the ``passed`` verdict, the ``MIN_SUBSTANTIVE_TOKENS`` floor,
the ``_are_sibling_variants`` exemption, and the ``_main`` exit codes — is
exercised rather than only dispatched.

The matcher walks the four canonical authoring subtrees under a project root
(``src/apothem/{rules,commands,skills,hooks/messages}``), so each case
materialises a throwaway corpus under ``tmp_path`` and drives the real entry
points against it.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "redundancy_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("redundancy_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["redundancy_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()

# A single paragraph carrying well over MIN_SUBSTANTIVE_TOKENS (40) distinct
# tokens. When it appears verbatim in two non-sibling files its self-similarity
# is 1.0, above the 0.80 default threshold — the canonical duplicate.
_SHARED_PARAGRAPH: Final[str] = (
    "The conformity validator walks every governed authoring tree and compares "
    "normalized paragraphs pairwise using jaccard similarity to surface "
    "substantively duplicated prose that erodes the demand load discipline "
    "across rules commands skills and hooks while excluding fenced code "
    "frontmatter binding tails companion anchors and canonical scaffolding "
    "headings from the comparison surface entirely before any finding is "
    "emitted for operator triage."
)

# Two paragraphs with near-disjoint vocabulary; their pairwise Jaccard sits far
# below the threshold, so a corpus carrying one of each is clean.
_DISTINCT_A: Final[str] = (
    "Apothem materializes harness native configuration files from one shared "
    "profile stored beneath the operator home directory, converting rules "
    "commands skills hooks output styles settings schemas and documentation "
    "into each vendor surface, while the conformity gate validates the synced "
    "unit before any adapter writes onto the local filesystem during "
    "installation."
)
_DISTINCT_B: Final[str] = (
    "The pytest suite exercises every registered adapter through a full round "
    "trip covering install uninstall update and verify actions, asserting "
    "golden fixtures match byte for byte, so a regression in projection or "
    "materialization is caught immediately inside continuous integration "
    "rather than reaching a tagged signed release artifact downstream."
)


def _write_corpus_file(root: Path, subtree: str, name: str, body: str) -> None:
    """Write ``body`` to ``<root>/<subtree>/<name>``, creating parents."""
    target = root / subtree / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body + "\n", encoding="utf-8")


def test_duplicate_paragraph_across_non_sibling_files_fails(tmp_path: Path) -> None:
    # Two non-sibling-variant stems (differ in both kebab positions, so
    # _are_sibling_variants is False) under rules/ sharing an identical
    # >40-token paragraph: a genuine cross-file duplicate.
    _write_corpus_file(
        tmp_path, "src/apothem/rules", "alpha-guidance.md", _SHARED_PARAGRAPH
    )
    _write_corpus_file(
        tmp_path, "src/apothem/rules", "beta-directive.md", _SHARED_PARAGRAPH
    )

    result = _MOD.check_corpus(tmp_path)

    assert result.passed is False, result.to_json()
    assert result.findings
    finding = result.findings[0]
    assert finding.similarity >= _MOD.DEFAULT_THRESHOLD
    assert finding.files == sorted(
        [
            (tmp_path / "src/apothem/rules/alpha-guidance.md").as_posix(),
            (tmp_path / "src/apothem/rules/beta-directive.md").as_posix(),
        ]
    )


def test_distinct_paragraphs_pass(tmp_path: Path) -> None:
    # Two files, each with a distinct >40-token paragraph whose pairwise
    # similarity is well below threshold: a clean corpus.
    _write_corpus_file(tmp_path, "src/apothem/rules", "alpha-guidance.md", _DISTINCT_A)
    _write_corpus_file(tmp_path, "src/apothem/rules", "beta-directive.md", _DISTINCT_B)

    result = _MOD.check_corpus(tmp_path)

    assert result.passed is True, result.to_json()
    assert result.findings == []
    # The two >40-token paragraphs both cleared the substantive-token floor
    # and entered comparison, so the scan was not vacuous.
    assert result.paragraph_count == 2


def test_sibling_variant_shared_paragraph_is_exempt(tmp_path: Path) -> None:
    # The same shared paragraph in two sibling-variant-named files in the same
    # directory (stems differ in exactly one kebab position). The canonical
    # sibling-variant exemption suppresses the pairing, so the corpus passes.
    _write_corpus_file(
        tmp_path,
        "src/apothem/hooks/messages",
        "pretooluse-edit-header-guard.md",
        _SHARED_PARAGRAPH,
    )
    _write_corpus_file(
        tmp_path,
        "src/apothem/hooks/messages",
        "pretooluse-write-header-guard.md",
        _SHARED_PARAGRAPH,
    )
    assert _MOD._are_sibling_variants(
        Path("pretooluse-edit-header-guard.md"),
        Path("pretooluse-write-header-guard.md"),
    )

    result = _MOD.check_corpus(tmp_path)

    assert result.passed is True, result.to_json()
    assert result.findings == []


def test_main_exit_codes(tmp_path: Path, capsys) -> None:
    # _main prints the JSON report and returns EXIT_FAIL on a duplicate corpus,
    # EXIT_PASS on a clean one.
    dup_root = tmp_path / "dup"
    clean_root = tmp_path / "clean"
    _write_corpus_file(
        dup_root, "src/apothem/rules", "alpha-guidance.md", _SHARED_PARAGRAPH
    )
    _write_corpus_file(
        dup_root, "src/apothem/rules", "beta-directive.md", _SHARED_PARAGRAPH
    )
    _write_corpus_file(
        clean_root, "src/apothem/rules", "alpha-guidance.md", _DISTINCT_A
    )
    _write_corpus_file(
        clean_root, "src/apothem/rules", "beta-directive.md", _DISTINCT_B
    )

    assert _MOD._main(["prog", str(dup_root)]) == _MOD.EXIT_FAIL
    assert _MOD._main(["prog", str(clean_root)]) == _MOD.EXIT_PASS
    # Each invocation emitted its JSON report to stdout.
    assert capsys.readouterr().out.count('"grep": "redundancy-grep"') == 2


def _every_pair(root: Path, threshold: float) -> list[tuple[list[str], float]]:
    """Compare every paragraph pair with no shortcut; return (files, similarity)."""
    entries = [
        (path, tokens)
        for path in _MOD._walk_corpus(root)
        for _text, tokens in _MOD._extract_paragraphs(path)
    ]
    found: list[tuple[list[str], float]] = []
    for i, (path_i, tokens_i) in enumerate(entries):
        for path_j, tokens_j in entries[i + 1 :]:
            if path_i == path_j or _MOD._are_sibling_variants(path_i, path_j):
                continue
            sim = len(tokens_i & tokens_j) / len(tokens_i | tokens_j)
            if sim >= threshold:
                pair = sorted({path_i.as_posix(), path_j.as_posix()})
                found.append((pair, round(sim, 4)))
    return found


def test_findings_match_an_every_pair_comparison(tmp_path: Path) -> None:
    # check_corpus skips pairs whose sizes alone rule out a match and caches the
    # sibling verdict per file pair. Its findings must equal a plain comparison
    # of every pair, in the same order, across paragraph sizes, overlaps,
    # sibling and non-sibling files, one folder and several.
    rng = random.Random(20261124)  # noqa: S311 - a fixed corpus, not a secret
    vocabulary = [
        "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(7))
        for _ in range(160)
    ]
    core = vocabulary[:40]

    def paragraph() -> str:
        extra = rng.sample(vocabulary[40:], rng.randint(0, 80))
        kept = rng.sample(core, rng.randint(30, 40))
        return " ".join(kept + extra)

    names = [
        ("src/apothem/rules", "alpha-guidance.md"),
        ("src/apothem/rules", "alpha-directive.md"),  # sibling of the first
        ("src/apothem/rules", "alpha-guidance-extra.md"),  # companion form
        ("src/apothem/rules", "beta-notes.md"),
        ("src/apothem/commands", "alpha-guidance.md"),  # same stem, other folder
        ("src/apothem/skills/gamma", "SKILL.md"),
        ("src/apothem/hooks/messages", "stop.md"),
    ]
    for subtree, name in names:
        body = "\n\n".join(paragraph() for _ in range(rng.randint(2, 4)))
        _write_corpus_file(tmp_path, subtree, name, body)

    for threshold in (0.3, 0.45, 0.6, 0.8):
        expected = _every_pair(tmp_path, threshold)
        result = _MOD.check_corpus(tmp_path, threshold=threshold)
        got = [(finding.files, finding.similarity) for finding in result.findings]
        assert got == expected, threshold
    # The corpus is not vacuous: the low thresholds report pairs, and some
    # pairs sit in one folder, so the sibling exemption is exercised.
    assert _every_pair(tmp_path, 0.3)
    assert _every_pair(tmp_path, 0.3) != _every_pair(tmp_path, 0.6)
