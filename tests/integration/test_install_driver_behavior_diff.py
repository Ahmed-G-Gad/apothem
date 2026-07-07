# SPDX-License-Identifier: MIT

"""Behavior-diff regression wall for the install_driver decomposition.

Re-runs the canonical behavior oracle and asserts the output is byte-identical
to the committed golden corpus at ``tests/fixtures/behavior-diff/install_driver/``.
Any future change that alters rendered native files, dispatch/dry-run results,
ledger records, or the run envelope is caught here. The corpus was captured
from the pre-decomposition god-module; this test is what proves the
decomposition (and every later edit) preserves behavior.

Coverage: plan + dry-run for ALL adapters (fast, no real I/O); full real-install
rendered tree + ledger + envelope for a representative subset spanning the
adapter shapes (user-scope settings + interpreter; project-scope rules-dir;
TOML agent conversion; project-scope TOML commands). The subset is an explicit,
budget-driven scope choice, not a silent cap — the full-matrix real-install
replay is available via ``_install_driver_oracle.capture_full``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from . import _behavior_canon as canon
from . import _install_driver_oracle as oracle

GOLDEN = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "behavior-diff"
    / "install_driver"
)

# Real-install byte-replay subset, chosen for adapter-shape diversity.
REAL_SUBSET = ["claude_code", "cursor", "codex", "gemini_cli"]


def _assert_tree_matches(actual_dir: Path, golden_dir: Path, label: str) -> None:
    actual_files = {
        p.relative_to(actual_dir) for p in actual_dir.rglob("*") if p.is_file()
    }
    golden_files = {
        p.relative_to(golden_dir) for p in golden_dir.rglob("*") if p.is_file()
    }
    assert actual_files == golden_files, (
        f"{label}: file-set drift — "
        f"only-actual={sorted(map(str, actual_files - golden_files))[:10]} "
        f"only-golden={sorted(map(str, golden_files - actual_files))[:10]}"
    )
    mismatches = [
        str(rel)
        for rel in sorted(actual_files)
        if canon.canon_file((actual_dir / rel).read_bytes())
        != canon.canon_file((golden_dir / rel).read_bytes())
    ]
    assert not mismatches, f"{label}: drift in {mismatches[:10]}"


def test_behavior_diff_plan_and_dryrun_all_adapters(tmp_path: Path) -> None:
    """plan/ + dryrun/ for every adapter must byte-match the committed golden."""
    out = tmp_path / "corpus"
    oracle.capture(out, fast_adapters=oracle.ALL_ADAPTERS, real_adapters=[])
    for sub in ("plan", "dryrun"):
        _assert_tree_matches(out / sub, GOLDEN / sub, sub)


def test_behavior_diff_real_install_representative(tmp_path: Path) -> None:
    """Real-install rendered tree + ledger + envelope for the representative subset."""
    out = tmp_path / "corpus"
    oracle.capture(out, fast_adapters=[], real_adapters=REAL_SUBSET)
    for name in REAL_SUBSET:
        _assert_tree_matches(
            out / "rendered" / name, GOLDEN / "rendered" / name, f"rendered/{name}"
        )
        assert canon.canon_ledger(
            (out / "ledger" / f"{name}.jsonl").read_bytes()
        ) == canon.canon_ledger((GOLDEN / "ledger" / f"{name}.jsonl").read_bytes()), (
            f"ledger/{name} drift"
        )
        assert canon.canon_render(
            (out / "envelope" / f"{name}.json").read_bytes()
        ) == canon.canon_render((GOLDEN / "envelope" / f"{name}.json").read_bytes()), (
            f"envelope/{name} drift"
        )


@pytest.mark.parametrize("name", oracle.ALL_ADAPTERS)
def test_golden_corpus_has_every_adapter(name: str) -> None:
    """The committed corpus must carry every registered adapter (no silent gap)."""
    assert (GOLDEN / "plan" / f"{name}.json").is_file()
    assert (GOLDEN / "dryrun" / f"{name}.json").is_file()
    assert (GOLDEN / "rendered" / name).is_dir()
