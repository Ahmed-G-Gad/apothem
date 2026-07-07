# SPDX-License-Identifier: MIT

"""Shared fixtures for the copilot-instructions-presence validator self-tests.

Each test runs against an isolated fake-ecosystem rooted at ``tmp_path``.
The fixture seeds a minimal ``.github/`` directory and patches the
module-level ``ECOSYSTEM_ROOT`` anchor so the working tree's real Copilot
surface is never consulted during a unit test.
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
    _REPO_ROOT
    / "src"
    / "apothem"
    / "conformity"
    / "copilot_instructions_presence_grep.py"
)

CANONICAL_BANNER_LINES: Final[tuple[str, ...]] = (
    "<!--",
    "# SPDX-License-Identifier: MIT",
    "#  Copyright (c) Ahmed G. Gad ----------------------  #",
    "#      Website:   https://ahmedgad.com                #",
    "#      Email:     mailto:me@ahmedgad.com              #",
    "#      Github:    https://github.com/ahmed-g-gad      #",
    "#  Licensed under MIT; see LICENSE for terms -------  #",
    "-->",
)
CANONICAL_BANNER: Final[str] = "\n".join(CANONICAL_BANNER_LINES) + "\n"

CANONICAL_SECTIONS: Final[tuple[str, ...]] = (
    "Project Context",
    "Coding Conventions",
    "File Headers",
    "Plans Discipline",
    "Structured Inquiry Behavior",
    "Forbidden Patterns",
    "Output Format",
    "Review Checklist",
    "Pointers",
)


def _load_grep_module() -> ModuleType:
    """Load the copilot-instructions-presence grep module via its source path."""
    spec = importlib.util.spec_from_file_location(
        "copilot_instructions_presence_grep", _GREP_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load grep module at {_GREP_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["copilot_instructions_presence_grep"] = module
    spec.loader.exec_module(module)
    return module


def _build_canonical_body(sections: tuple[str, ...] = CANONICAL_SECTIONS) -> str:
    """Render a well-formed Copilot-surface body."""
    parts: list[str] = [CANONICAL_BANNER, "", "# GitHub Copilot Instructions", ""]
    for section in sections:
        parts.extend([f"## {section}", "", f"Body for {section}.", ""])
    return "\n".join(parts) + "\n"


@pytest.fixture
def grep_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> ModuleType:
    """Provide a freshly loaded grep module rooted at ``tmp_path``."""
    module = _load_grep_module()
    (tmp_path / ".github").mkdir()
    monkeypatch.setattr(module, "ECOSYSTEM_ROOT", tmp_path)
    return module


@pytest.fixture
def canonical_body() -> str:
    """A well-formed Copilot-surface body with all nine canonical sections."""
    return _build_canonical_body()


@pytest.fixture
def build_body() -> Callable[[tuple[str, ...]], str]:
    """Return a helper that renders a Copilot-surface body with given sections."""

    def _builder(sections: tuple[str, ...]) -> str:
        return _build_canonical_body(sections)

    return _builder


@pytest.fixture
def write_target(tmp_path: Path) -> Callable[[str], Path]:
    """Return a helper that writes the body at the canonical path under tmp_path."""

    def _writer(body: str) -> Path:
        target = tmp_path / ".github" / "copilot-instructions.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return target

    return _writer
