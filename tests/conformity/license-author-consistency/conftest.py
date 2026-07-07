# SPDX-License-Identifier: MIT

"""Shared fixtures for the license-author-consistency validator self-tests.

Each test runs against an isolated fake-ecosystem rooted at ``tmp_path``.
Under the narrowed authorship-header contract the validator inspects a
single surface — the root ``LICENSE`` author line — so the fixture only
patches the module-level ``ECOSYSTEM_ROOT`` anchor and lets each test write
the LICENSE it needs. The working tree's real LICENSE is never consulted
during a unit test.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "license_author_consistency_grep.py"
)


def _load_grep_module() -> ModuleType:
    """Load the license-author-consistency grep module via its source path."""
    spec = importlib.util.spec_from_file_location(
        "license_author_consistency_grep", _GREP_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load grep module at {_GREP_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["license_author_consistency_grep"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def grep_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> ModuleType:
    """Provide a freshly loaded grep module rooted at ``tmp_path``."""
    module = _load_grep_module()
    monkeypatch.setattr(module, "ECOSYSTEM_ROOT", tmp_path)
    return module


@pytest.fixture
def write_license(tmp_path: Path) -> Callable[[str], Path]:
    """Return a helper that writes the LICENSE body under ``tmp_path``."""

    def _writer(body: str) -> Path:
        target = tmp_path / "LICENSE"
        target.write_text(body, encoding="utf-8")
        return target

    return _writer
