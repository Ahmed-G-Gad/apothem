# SPDX-License-Identifier: MIT

"""Regression test for the orphan-output-grep py.typed carve-out.

PEP 561 defines ``py.typed`` as a marker file --- conventionally zero-byte ---
that signals a package ships inline type information for downstream importers.
A per-file provenance banner would defeat the zero-byte marker convention, and
the marker's provenance is structural: the package contract ships it (the
``apothem`` ``[tool.setuptools.package-data]`` entry in ``pyproject.toml``). So
``py.typed`` is carved out of the provenance requirement, exactly as the
machine-parseable ``.SRCINFO`` manifest is; a non-marker sibling is NOT.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "orphan_output_grep.py"
)


def _load_grep() -> ModuleType:
    """Load the orphan-output-grep module from the tree under test."""
    spec = importlib.util.spec_from_file_location(
        "orphan_output_grep_under_test_pytyped", _GREP_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["orphan_output_grep_under_test_pytyped"] = module
    spec.loader.exec_module(module)
    return module


def test_py_typed_marker_is_provenance_exempt() -> None:
    """An empty py.typed marker is NOT flagged for absent provenance."""
    grep = _load_grep()
    path = _REPO_ROOT / "src" / "apothem" / "py.typed"

    result = grep.check("", path)

    assert result.passed is True
    assert result.findings == []


def test_py_typed_basename_is_in_carveout_set() -> None:
    """The carve-out set names py.typed explicitly (guards an accidental drop)."""
    grep = _load_grep()
    assert "py.typed" in grep.TRIVIAL_PROVENANCE_BASENAMES
