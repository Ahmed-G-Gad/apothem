# SPDX-License-Identifier: MIT

"""Shared fixtures for the plan-write-guard hook self-tests.

The plan-write-guard hook is advisory: the hook context messages at
``src/apothem/hooks/messages/pretooluse-write-plan-guard.md`` and
``src/apothem/hooks/messages/pretooluse-bash-plan-guard.md`` declare the predicate the
operating agent applies. These tests verify the hook contexts' specification
contract — the file is present at the canonical path, declares the expected
verdicts (redirect-required / recursion-self allow / soft-flag / allow),
declares the structured inquiry option shapes for each verdict class, and
declares the advisory two-layer fail-disposition (dispatcher fail-open).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_HOOKS_MESSAGES_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem" / "hooks" / "messages"
# Native-install fixtures live under the per-harness example tree, not at
# the repo root.
_NATIVE_INSTALL_DIR: Final[Path] = (
    _REPO_ROOT / "examples" / "harnesses" / "claude-code" / "native-install"
)


@pytest.fixture
def repo_root() -> Path:
    """Absolute path to the ecosystem root."""
    return _REPO_ROOT


@pytest.fixture
def write_plan_guard_text() -> str:
    """Body of the Write/Edit/NotebookEdit plan-write-guard context."""
    target = _HOOKS_MESSAGES_DIR / "pretooluse-write-plan-guard.md"
    return target.read_text(encoding="utf-8")


@pytest.fixture
def bash_plan_guard_text() -> str:
    """Body of the Bash plan-write-guard companion context."""
    target = _HOOKS_MESSAGES_DIR / "pretooluse-bash-plan-guard.md"
    return target.read_text(encoding="utf-8")


@pytest.fixture
def settings_json() -> dict[str, object]:
    """Parsed contents of the canonical Claude Code settings.json."""
    return json.loads(
        (_NATIVE_INSTALL_DIR / "settings.json").read_text(encoding="utf-8")
    )
