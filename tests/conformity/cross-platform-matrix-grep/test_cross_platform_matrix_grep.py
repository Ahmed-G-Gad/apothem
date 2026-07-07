# SPDX-License-Identifier: MIT

"""Driver test for the cross-platform-matrix matcher against its fixtures.

The orphaned ``pass/`` and ``fail/`` fixture trees beside this file carry a
canonical CI-matrix workflow and a deficient one. This driver runs
``check(root)`` against each: the pass fixture declares the full 3-OS x
4-Python matrix and must pass; the fail fixture omits ``macos-latest`` and
Python 3.13 and must fail with the matching drift classes. A third test
confirms a root with no workflow yields the informational not-yet-materialised
pass.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "cross_platform_matrix_grep.py"
)
_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "cross_platform_matrix_grep", _GREP_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cross_platform_matrix_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def _stage_fixture(tmp_path: Path, which: str) -> Path:
    """Copy a fixture's ci-matrix.yml into a .github/workflows/ tree."""
    src = _FIXTURE_DIR / which / "ci-matrix.yml"
    assert src.exists(), f"missing fixture {src}"
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci-matrix.yml").write_text(
        src.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def test_pass_fixture_passes(tmp_path: Path) -> None:
    root = _stage_fixture(tmp_path, "pass")
    result = _MOD.check(root)
    assert result.passed, result.to_json()
    assert not result.not_yet_materialised
    assert result.findings == []


def test_fail_fixture_fails(tmp_path: Path) -> None:
    root = _stage_fixture(tmp_path, "fail")
    result = _MOD.check(root)
    assert not result.passed
    classes = {f.drift_class for f in result.findings}
    # The fail fixture omits macos-latest and Python 3.13.
    assert "os-missing" in classes
    assert "python-version-missing" in classes


def test_absent_workflow_is_informational_pass(tmp_path: Path) -> None:
    result = _MOD.check(tmp_path)
    assert result.passed
    assert result.not_yet_materialised


_WORKFLOW_TEMPLATE = """\
name: ci-matrix
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ${{{{ matrix.os }}}}
    strategy:
      fail-fast: false
      matrix:
        os: [{os}]
        python-version: [{py}]
    steps:
      - run: python -m pytest
"""


def _stage_inline(
    tmp_path: Path, *, os_line: str, py_line: str, classifiers: str | None
) -> Path:
    """Stage a synthetic ci-matrix workflow plus an optional pyproject.toml."""
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci-matrix.yml").write_text(
        _WORKFLOW_TEMPLATE.format(os=os_line, py=py_line), encoding="utf-8"
    )
    if classifiers is not None:
        (tmp_path / "pyproject.toml").write_text(classifiers, encoding="utf-8")
    return tmp_path


def test_required_python_derived_from_pyproject_classifiers(tmp_path: Path) -> None:
    # A pyproject declaring 3.10-3.14 makes 3.14 part of the required set: a
    # matrix that stops at 3.13 must now be flagged for the missing 3.14 lane.
    classifiers = "\n".join(
        f'  "Programming Language :: Python :: {v}",'
        for v in ("3.10", "3.11", "3.12", "3.13", "3.14")
    )
    root = _stage_inline(
        tmp_path,
        os_line="ubuntu-latest, macos-latest, windows-latest",
        py_line='"3.10", "3.11", "3.12", "3.13"',
        classifiers=f"[project]\nclassifiers = [\n{classifiers}\n]\n",
    )
    result = _MOD.check(root)
    assert not result.passed
    classes = {f.drift_class for f in result.findings}
    assert "python-version-missing" in classes
    assert any("3.14" in f.detail for f in result.findings)


def test_full_derived_python_set_passes(tmp_path: Path) -> None:
    # When the matrix covers the full classifier-derived set (3.10-3.14) the
    # sweep is clean — the derived set, not a hardcoded 4-version list, governs.
    classifiers = "\n".join(
        f'  "Programming Language :: Python :: {v}",'
        for v in ("3.10", "3.11", "3.12", "3.13", "3.14")
    )
    root = _stage_inline(
        tmp_path,
        os_line="ubuntu-latest, macos-latest, windows-latest",
        py_line='"3.10", "3.11", "3.12", "3.13", "3.14"',
        classifiers=f"[project]\nclassifiers = [\n{classifiers}\n]\n",
    )
    result = _MOD.check(root)
    assert result.passed, result.to_json()


def test_versioned_runner_labels_credit_os_family(tmp_path: Path) -> None:
    # Pinned runner images (ubuntu-24.04, macos-15, windows-2025) are credited
    # to their OS family — a pinned-image matrix passes the OS axis.
    classifiers = "\n".join(
        f'  "Programming Language :: Python :: {v}",'
        for v in ("3.10", "3.11", "3.12", "3.13", "3.14")
    )
    root = _stage_inline(
        tmp_path,
        os_line="ubuntu-24.04, macos-15, windows-2025",
        py_line='"3.10", "3.11", "3.12", "3.13", "3.14"',
        classifiers=f"[project]\nclassifiers = [\n{classifiers}\n]\n",
    )
    result = _MOD.check(root)
    assert result.passed, result.to_json()
    classes = {f.drift_class for f in result.findings}
    assert "os-missing" not in classes


def test_fallback_python_set_when_no_pyproject(tmp_path: Path) -> None:
    # With no pyproject.toml the fallback set (through 3.14) governs, so a
    # 4-version matrix is flagged for the missing 3.14 lane.
    root = _stage_inline(
        tmp_path,
        os_line="ubuntu-latest, macos-latest, windows-latest",
        py_line='"3.10", "3.11", "3.12", "3.13"',
        classifiers=None,
    )
    result = _MOD.check(root)
    assert not result.passed
    assert any("3.14" in f.detail for f in result.findings)
