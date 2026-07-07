# SPDX-License-Identifier: MIT

"""Validator's per-file verdicts aggregate correctly across a mixed
fixture directory.

The file-header grep is per-file by design; aggregate coverage is the
operator's responsibility (or the orchestrator's). This test seeds a
mixed-fixture directory with one file per outcome class and verifies
that running ``check()`` over each entry produces the expected
pass/fail tally."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_aggregate_coverage_pct(
    grep_module: ModuleType,
    canonical_block: str,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """Three applicable files (one canonical, one absent, one malformed)
    plus one exempt file produce coverage = 1/3 (33.3%) on applicable
    files. The exempt file is excluded from the denominator."""
    canonical_path = write_fixture("src/canonical.py", canonical_block + "x = 1\n")
    absent_path = write_fixture("src/absent.py", "x = 2\n")
    malformed_path = write_fixture(
        "src/malformed.py",
        "# Copyright (c) Ahmed G. Gad\n# Website\nx = 3\n",
    )
    exempt_path = write_fixture("src/exempt.json", '{"x": 4}\n')

    targets = [canonical_path, absent_path, malformed_path, exempt_path]
    results = [grep_module.check(p.read_text(encoding="utf-8"), p) for p in targets]

    pass_count = sum(1 for r in results if r.passed)
    fail_count = sum(1 for r in results if not r.passed)
    applicable = [
        r for r, p in zip(results, targets, strict=True) if "exempt" not in p.name
    ]
    canonical_count = sum(1 for r in applicable if r.passed)

    # exempt + canonical pass; absent + malformed fail
    assert pass_count == 2
    assert fail_count == 2
    # On the three applicable files, exactly one is canonical
    assert canonical_count == 1
    # Coverage on applicable files = 1/3
    assert canonical_count / len(applicable) == 1 / 3
