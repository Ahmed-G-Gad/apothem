# SPDX-License-Identifier: MIT

"""Replay every fuzz target over its seed corpus, without Atheris.

The targets in this folder run under Atheris in ClusterFuzzLite
(``.github/workflows/fuzzing.yml``), which needs Linux. Each target's
``fuzz_one_input`` is plain Python, so this test runs it over the seeds under
``seeds/<target>/`` on every CI cell, Windows included: a seed is a known input,
often one a fuzzer once crashed on, and must keep passing every invariant.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

_HERE = Path(__file__).resolve().parent
_TARGETS = sorted(_HERE.glob("fuzz_*.py"))


def _seed_dir(target: Path) -> Path:
    return _HERE / "seeds" / target.stem.removeprefix("fuzz_").replace("_", "-")


def _load(target: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_apothem_{target.stem}", target)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CASES = [
    pytest.param(target, seed, id=f"{target.stem}/{seed.name}")
    for target in _TARGETS
    for seed in sorted(_seed_dir(target).glob("*.txt"))
]


def test_every_target_has_seeds() -> None:
    assert _TARGETS, "no fuzz_*.py target found"
    for target in _TARGETS:
        assert list(_seed_dir(target).glob("*.txt")), f"{target.name} has no seeds"


@pytest.mark.parametrize(("target", "seed"), _CASES)
def test_seed_passes_the_target(target: Path, seed: Path) -> None:
    fuzz_one_input: Callable[[bytes], None] = _load(target).fuzz_one_input
    fuzz_one_input(seed.read_bytes())
