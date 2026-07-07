# SPDX-License-Identifier: MIT

"""In-process conformance tests for the standalone corpus-level greps.

The standalone validators in ``apothem.conformity`` walk a root directory
and exit 0 (PASS) or non-zero (FAIL). The conformity gate runs them via
subprocess in ``--all`` mode, so their behaviour is exercised end-to-end
but never attributed to in-process coverage. These tests import each
module and invoke its ``check(root)`` callable directly against the
repository root: the same surface the green ``gate --all`` CI job
asserts, run in-process so a regression that raises (import error,
traversal bug, signature drift) is caught by the unit suite rather than
only at the subprocess gate.

Every standalone grep is expected to PASS against this repository, which
is itself maintained conformant. A failure here is a real conformance
regression, not a test artefact.
"""

from __future__ import annotations

import dataclasses
import importlib
from pathlib import Path

import pytest

from apothem.conformity import gate

# Substrings that mark a GrepResult field as an inspection count rather than a
# verdict or a finding list. Each standalone grep names its count field by this
# convention (``scanned_count``, ``files_inspected``, ``folders_inspected``,
# ``harnesses_present``, ``workflow_count``, ``cells_checked``, ``*_total`` …),
# so the non-vacuous-pass guard below recognises them without a per-grep map.
_COUNT_FIELD_TOKENS: tuple[str, ...] = (
    "count",
    "inspected",
    "present",
    "checked",
    "scanned",
    "total",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Standalone modules excluded from this in-process root-only sweep, each with a
# per-entry justification. The remaining ``gate.STANDALONE_MODULES`` entries all
# expose the uniform ``check(root: Path) -> GrepResult`` corpus-walk entry point
# and are swept below; ``test_check_root_greps_partition_standalone_modules``
# asserts the partition so the derivation cannot drift from the gate registry.
#
# Two exclusion classes:
#
# (a) No uniform ``check(root)`` entry point — the module is argv-driven, walks
#     the git diff, or takes a different signature, so it cannot be invoked with
#     a bare repo-root path:
#       * ``naming_grep``            — ``check(target, is_dir)`` (per-path, two args)
#       * ``redundancy_grep``        — argv-driven, no ``check()``
#       * ``conventional_commit_grep``— change-set-scoped, no ``check()``
#       * ``harden_runner_grep``     — argv-driven, no ``check()``
#
# (b) Exposes ``check(root)`` but validates a fixed committed surface (the git
#     index, a named anchor-file set, or plan-suite infrastructure) rather than
#     the general working-tree corpus, so a bare root-root pass carries no
#     signal here; each has dedicated fixture coverage under
#     ``tests/conformity/<name>/``:
#       * ``smoke_install_grep``            — the paired install scripts at the root
#       * ``no_global_plans_grep``          — the git index for tracked plans paths
#       * ``plans_discipline_language_grep``— four named instruction surfaces
#       * ``plan_next_step_consistency_grep``— plan-suite infra footers (advisory)
#       * ``binding_reciprocity_corpus_grep``— the cross-file ↔-reciprocity walk
_ROOT_SWEEP_EXCLUDED_MODULES: frozenset[str] = frozenset(
    {
        "naming_grep",
        "redundancy_grep",
        "conventional_commit_grep",
        "harden_runner_grep",
        "smoke_install_grep",
        "no_global_plans_grep",
        "plans_discipline_language_grep",
        "plan_next_step_consistency_grep",
        "binding_reciprocity_corpus_grep",
    }
)

# The standalone greps exposing the uniform ``check(root: Path) -> GrepResult``
# in-process entry point. Derived from ``gate.STANDALONE_MODULES`` (hyphenated
# module names, normalised to the underscore import form) minus the explicit
# exclusion set above, so a newly registered corpus-walk grep is picked up by
# this sweep automatically.
_CHECK_ROOT_GREPS: tuple[str, ...] = tuple(
    name.replace("-", "_")
    for name in gate.STANDALONE_MODULES
    if name.replace("-", "_") not in _ROOT_SWEEP_EXCLUDED_MODULES
)

# Greps whose legitimate state against the *committed* repository is a
# zero-inspection pass. ``plan_suite_structure_grep`` walks the canonical
# ``<root>/.apothem/plans/`` tree, but plan suites are gitignored working state
# (``.gitignore`` names ``.apothem/plans/`` and directs operators to
# ``apothem migrate-workspace`` for any legacy tree), so a clean checkout
# carries no suite to inspect: its ``suite_count`` is 0 by design, and the
# grep's own docstring documents the vacuous pass on an absent or empty plans
# tree. Such greps still assert shape + verdict below, but are exempt from the
# non-vacuous-count guard, which would otherwise mistake a correct empty scan
# for a stale one. Their violation-detection paths are covered by dedicated
# fixture tests (e.g. ``tests/conformity/plan-suite-structure-grep/``).
_LEGITIMATELY_EMPTY_ROOT_GREPS: tuple[str, ...] = ("plan_suite_structure_grep",)


@pytest.mark.parametrize("module_name", _CHECK_ROOT_GREPS)
def test_standalone_grep_passes_against_repo_root(module_name: str) -> None:
    """Each standalone grep's ``check(repo_root)`` returns a passing result."""
    module = importlib.import_module(f"apothem.conformity.{module_name}")
    result = module.check(_REPO_ROOT)

    # The result duck-types a GrepResult: a boolean ``passed`` plus an
    # iterable ``findings``. Assert the shape, then the verdict.
    assert isinstance(result.passed, bool), (
        f"{module_name}.check() returned a non-boolean .passed"
    )
    assert result.passed, (
        f"{module_name} flagged the repository as non-conformant: "
        f"{[str(f) for f in result.findings]}"
    )

    # Defense against the vacuous-pass trap: a grep that scans nothing — a
    # stale scan root, a not-yet-materialised surface — reports ``passed=True``
    # with no findings while having inspected zero files. Where the result
    # exposes an inspection-count field (the ``*_count`` / ``*_inspected`` /
    # ``*_present`` / ``*_checked`` / ``*_total`` convention), assert at least
    # one such count is positive against the populated repository root, so a
    # silent empty scan is caught here rather than passing unnoticed. Pure
    # presence checks expose no count field and are inherently non-vacuous
    # (they fail when the required artifact is absent), so they are exempt.
    if (
        dataclasses.is_dataclass(result)
        and module_name not in _LEGITIMATELY_EMPTY_ROOT_GREPS
    ):
        counts = {
            f.name: value
            for f in dataclasses.fields(result)
            if not isinstance((value := getattr(result, f.name)), bool)
            and isinstance(value, int)
            and any(token in f.name for token in _COUNT_FIELD_TOKENS)
        }
        if counts:
            assert any(value > 0 for value in counts.values()), (
                f"{module_name} passed but reported zero inspected items "
                f"across {sorted(counts)} — a vacuous pass on an empty or "
                f"stale scan root"
            )


def test_check_root_greps_partition_standalone_modules() -> None:
    """The swept set and the exclusion set partition ``STANDALONE_MODULES``.

    ``_CHECK_ROOT_GREPS`` is derived from ``gate.STANDALONE_MODULES`` minus
    ``_ROOT_SWEEP_EXCLUDED_MODULES``, so the two together must exactly cover
    the gate registry with no overlap and no stray name. Asserting the
    partition makes the derivation self-checking: a newly registered
    standalone grep is either swept here or listed (with its per-entry
    justification) in the exclusion set — it cannot silently miss this
    sweep, and a typo in the exclusion set is caught immediately.
    """
    standalone = {name.replace("-", "_") for name in gate.STANDALONE_MODULES}
    swept = set(_CHECK_ROOT_GREPS)

    # No name appears in both halves.
    assert not (swept & _ROOT_SWEEP_EXCLUDED_MODULES), (
        "modules present in both the swept set and the exclusion set: "
        f"{sorted(swept & _ROOT_SWEEP_EXCLUDED_MODULES)}"
    )
    # Together the two halves cover exactly the gate registry.
    assert swept | _ROOT_SWEEP_EXCLUDED_MODULES == standalone, (
        "the swept + excluded partition does not match STANDALONE_MODULES; "
        f"missing={sorted(standalone - (swept | _ROOT_SWEEP_EXCLUDED_MODULES))}, "
        f"stray={sorted((swept | _ROOT_SWEEP_EXCLUDED_MODULES) - standalone)}"
    )


def test_excluded_modules_are_real_standalone_modules() -> None:
    """Every excluded name is a real ``STANDALONE_MODULES`` entry.

    Guards against an exclusion entry that names a module the gate registry
    does not carry (a rename or a typo), which would otherwise silently
    shrink the swept set.
    """
    standalone = {name.replace("-", "_") for name in gate.STANDALONE_MODULES}
    stray = _ROOT_SWEEP_EXCLUDED_MODULES - standalone
    assert not stray, f"exclusion set names non-registered modules: {sorted(stray)}"
