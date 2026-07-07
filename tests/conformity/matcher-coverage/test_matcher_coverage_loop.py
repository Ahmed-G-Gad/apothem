# SPDX-License-Identifier: MIT

"""Mechanized coverage loop: every conformity matcher carries a regression fixture.

Why this loop exists. The conformity matchers under
``src/apothem/conformity/`` are the mechanical fraction of the pre-emission
gate; each is enumerated in ``gate.py`` as ``GREP_MODULES`` (per-Write
matchers) or ``STANDALONE_MODULES`` (corpus-level validators). A matcher that
ships without a pass+fail regression fixture is a silent coverage gap — a
future regression in its verdict would surface only in production, not in the
unit suite. This loop reads the matcher inventory dynamically from ``gate.py``
(so it self-updates as matchers are added) and asserts, one parametrized case
per matcher, that the matcher has both a resolvable test directory carrying a
regression fixture and an importable module exposing its expected entry point.

Fixture forms. A regression fixture in this repository takes one of three
equivalent shapes inside the matcher's test directory: (1) a ``test_*.py``
with pass+fail assertions; (2) a ``pass.*`` + ``fail.*`` content-file pair
exercised by a matcher self-test; (3) a ``pass`` + ``fail`` corpus-directory
pair walked by a standalone-grep root scan. Any one of the three satisfies the
coverage requirement; the loop recognises all three so it stays green against
the repository's existing mixed fixture conventions.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_CONFORMITY_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem" / "conformity"
_TEST_DIR: Final[Path] = _REPO_ROOT / "tests" / "conformity"
_GATE_PATH: Final[Path] = _CONFORMITY_DIR / "gate.py"

# Change-set-scoped matcher documented inline in gate.py but deliberately
# excluded from the per-Write GREP_MODULES registry (it operates on the git
# diff, not a single Write). It still ships a matcher module and a regression
# fixture, so the coverage loop holds it to the same bar.
_CHANGE_SET_SCOPED: Final[tuple[str, ...]] = ("semver_stability_grep",)


def _load_gate() -> ModuleType:
    """Load the gate orchestrator so its matcher inventory tuples can be read."""
    spec = importlib.util.spec_from_file_location("gate", _GATE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["gate"] = module
    spec.loader.exec_module(module)
    return module


def _matcher_inventory() -> tuple[str, ...]:
    """Read the authoritative matcher inventory from gate.py at collection time.

    The union of ``GREP_MODULES`` and ``STANDALONE_MODULES`` (normalised to
    underscore module-name form) plus the change-set-scoped module gate.py
    documents inline. Reading the tuples here — rather than hardcoding a copy —
    makes the loop self-update: a matcher added to either gate tuple is picked
    up by this loop automatically and fails until it carries a fixture.
    """
    gate = _load_gate()
    names = {name.replace("-", "_") for name in gate.GREP_MODULES}
    names.update(name.replace("-", "_") for name in gate.STANDALONE_MODULES)
    names.update(_CHANGE_SET_SCOPED)
    return tuple(sorted(names))


def _resolve_test_dir(module_name: str) -> Path | None:
    """Resolve a matcher's test directory under ``tests/conformity/``.

    Maps the underscore module name to kebab-case, then tries the bare
    kebab form and the ``<kebab>-grep`` form. Returns the first directory
    that exists, or None when no directory is found.
    """
    kebab = module_name.replace("_", "-")
    candidates = [_TEST_DIR / kebab, _TEST_DIR / f"{kebab}-grep"]
    if kebab.endswith("-grep"):
        candidates.append(_TEST_DIR / kebab[: -len("-grep")])
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _has_regression_fixture(test_dir: Path) -> bool:
    """Return True iff the directory carries a pass+fail regression fixture.

    Three equivalent fixture forms are recognised: a ``test_*.py``; a
    ``pass.*`` + ``fail.*`` content-file pair; or a ``pass`` + ``fail``
    corpus-directory pair (used by standalone greps that walk a root).
    """
    if any(test_dir.glob("test_*.py")):
        return True
    has_pass = any(test_dir.glob("pass*"))
    has_fail = any(test_dir.glob("fail*"))
    return has_pass and has_fail


def _load_matcher_module(module_name: str) -> ModuleType | None:
    """Load a matcher module from the conformity package by spec.

    Returns the loaded module, or None when no module file exists for the
    name (which is itself a coverage failure surfaced by the caller).
    """
    module_path = _CONFORMITY_DIR / f"{module_name}.py"
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_INVENTORY: Final[tuple[str, ...]] = _matcher_inventory()


def test_inventory_is_non_empty() -> None:
    """The matcher inventory read from gate.py is non-empty (guards a parse bug)."""
    assert _INVENTORY, "gate.py exposed no matchers — inventory read failed"


@pytest.mark.parametrize("module_name", _INVENTORY)
def test_matcher_has_regression_fixture(module_name: str) -> None:
    """Every matcher resolves a test directory carrying a pass+fail fixture.

    A matcher with no fixture directory, or a directory with no recognisable
    regression fixture, is a blocking coverage finding — a failing test, not a
    silent omission.
    """
    test_dir = _resolve_test_dir(module_name)
    assert test_dir is not None, (
        f"matcher {module_name!r} has no test directory under {_TEST_DIR}; "
        f"every matcher MUST ship a pass+fail regression fixture"
    )
    assert _has_regression_fixture(test_dir), (
        f"matcher {module_name!r} test directory {test_dir.name!r} carries no "
        f"regression fixture (expected a test_*.py, a pass.*/fail.* pair, or a "
        f"pass/fail corpus-directory pair)"
    )


@pytest.mark.parametrize("module_name", _INVENTORY)
def test_matcher_module_imports_and_exposes_entry(module_name: str) -> None:
    """Every matcher module imports and exposes a `check` or CLI `_main` entry."""
    module = _load_matcher_module(module_name)
    assert module is not None, (
        f"matcher {module_name!r} has no module file under {_CONFORMITY_DIR}"
    )
    has_check = callable(getattr(module, "check", None))
    has_main = callable(getattr(module, "_main", None)) or callable(
        getattr(module, "main", None)
    )
    assert has_check or has_main, (
        f"matcher {module_name!r} exposes neither a check() nor a _main() entry"
    )
