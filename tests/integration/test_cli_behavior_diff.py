# SPDX-License-Identifier: MIT

"""Behavior-diff regression wall for the cli/__init__.py decomposition.

Re-runs the CLI behavior oracle and asserts the output is byte-identical to the
committed golden corpus at ``tests/fixtures/behavior-diff/cli/``. The corpus was
captured from the pre-decomposition monolithic ``cli/__init__.py``; this test is
what proves the decomposition (and every later edit) preserves the observable
CLI behavior — every command's stdout, JSON envelope, and exit code across the
fixed invocation matrix.
"""

from __future__ import annotations

from pathlib import Path

from . import _behavior_canon as canon
from . import _cli_oracle as oracle

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "behavior-diff" / "cli"


def test_behavior_diff_cli_matrix_is_byte_identical(tmp_path: Path) -> None:
    """Every CLI invocation's normalized record must byte-match the committed golden."""
    out = tmp_path / "cli"
    count = oracle.capture(out)

    actual = {
        p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*.json")
    }
    golden = {
        p.relative_to(GOLDEN).as_posix(): p.read_bytes() for p in GOLDEN.rglob("*.json")
    }

    assert set(actual) == set(golden), (
        "fixture-set drift — "
        f"only-actual={sorted(set(actual) - set(golden))} "
        f"only-golden={sorted(set(golden) - set(actual))}"
    )
    mismatches = [
        slug
        for slug in sorted(actual)
        if canon.canon_render(actual[slug]) != canon.canon_render(golden[slug])
    ]
    if mismatches:
        detail = "\n".join(
            f"  {slug}: "
            + canon.first_diff(
                canon.canon_render(golden[slug]), canon.canon_render(actual[slug])
            )
            for slug in mismatches[:5]
        )
        raise AssertionError(f"drift in {mismatches}\n{detail}")
    assert count == len(golden)


def test_golden_corpus_covers_the_matrix() -> None:
    """Every matrix invocation has a committed golden fixture (no silent gap)."""
    for slug, _argv, _seed in oracle.matrix():
        assert (GOLDEN / f"{slug}.json").is_file(), f"missing golden fixture: {slug}"
