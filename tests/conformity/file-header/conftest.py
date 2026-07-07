# SPDX-License-Identifier: MIT

"""Shared fixtures for the file-header validator self-tests.

Each test runs against an isolated fake-ecosystem rooted at ``tmp_path``.
The fixture seeds a minimal ``src/apothem/schemas/authorship-header.txt`` and
``src/apothem/schemas/header-exceptions.txt`` so the validator's filesystem reads
resolve cleanly, and patches the module-level ECOSYSTEM_ROOT /
SCHEMAS_DIR anchors so the working tree's real fixtures are never
consulted during a unit test."""

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
    _REPO_ROOT / "src" / "apothem" / "conformity" / "file_header_grep.py"
)

CANONICAL_BANNER_LINES: Final[tuple[str, ...]] = ("# SPDX-License-Identifier: MIT",)
CANONICAL_BLOCK: Final[str] = "\n".join(CANONICAL_BANNER_LINES) + "\n\n"

# The retired branded banner, kept only as a malformed fixture: it still
# carries the legacy author marker but no longer matches the canonical
# single-line form, so the validator reports it as HEADER_MALFORMED.
LEGACY_BANNER_LINES: Final[tuple[str, ...]] = (
    "# SPDX-License-Identifier: MIT",
    "#  Copyright (c) Ahmed G. Gad ----------------------  #",
    "#      Website:   https://ahmedgad.com                #",
    "#      Email:     mailto:me@ahmedgad.com              #",
    "#      Github:    https://github.com/ahmed-g-gad      #",
    "#  Licensed under MIT; see LICENSE for terms -------  #",
)
LEGACY_BLOCK: Final[str] = "\n".join(LEGACY_BANNER_LINES) + "\n\n"


def _load_grep_module() -> ModuleType:
    """Load the file-header grep module via its real source path."""
    spec = importlib.util.spec_from_file_location("file_header_grep", _GREP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load grep module at {_GREP_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["file_header_grep"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def grep_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> ModuleType:
    """Provide a freshly loaded grep module rooted at ``tmp_path``."""
    module = _load_grep_module()
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    (schemas_dir / "authorship-header.txt").write_text(
        "\n".join(CANONICAL_BANNER_LINES) + "\n",
        encoding="utf-8",
    )
    (schemas_dir / "header-exceptions.txt").write_text(
        "# test exception list\n**/*.json\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ECOSYSTEM_ROOT", tmp_path)
    monkeypatch.setattr(module, "SCHEMAS_DIR", schemas_dir)
    return module


@pytest.fixture
def canonical_block() -> str:
    """The canonical banner block plus mandatory trailing blank line."""
    return CANONICAL_BLOCK


@pytest.fixture
def write_fixture(tmp_path: Path) -> Callable[[str, str], Path]:
    """Return a helper that writes content under ``tmp_path``."""

    def _writer(relative: str, body: str) -> Path:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return target

    return _writer
