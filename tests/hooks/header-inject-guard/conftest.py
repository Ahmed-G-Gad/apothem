# SPDX-License-Identifier: MIT

"""Shared fixtures for the header-inject-guard hook self-tests.

Each test simulates a harness-dispatched PreToolUse Write/Edit by
piping a tool-input JSON envelope to the conformity-gate orchestrator
and inspecting the resulting orchestrator report. The orchestrator's
verdict is the trigger condition the hook context message reacts to.
"""

from __future__ import annotations

import importlib.util
import json
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
_HOOKS_MESSAGES_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem" / "hooks" / "messages"

CANONICAL_BANNER_LINES: Final[tuple[str, ...]] = ("# SPDX-License-Identifier: MIT",)
CANONICAL_BLOCK: Final[str] = "\n".join(CANONICAL_BANNER_LINES) + "\n\n"


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
    """A grep module rooted at ``tmp_path`` with minimal seed fixtures."""
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
def write_guard_path() -> Path:
    """Absolute path to the Write-route header-inject-guard context."""
    return _HOOKS_MESSAGES_DIR / "pretooluse-write-header-guard.md"


@pytest.fixture
def edit_guard_path() -> Path:
    """Absolute path to the Edit-route header-inject-guard context."""
    return _HOOKS_MESSAGES_DIR / "pretooluse-edit-header-guard.md"


@pytest.fixture
def repo_root() -> Path:
    """Absolute path to the ecosystem root (used by orchestrator tests)."""
    return _REPO_ROOT


@pytest.fixture
def make_envelope() -> Callable[..., str]:
    """Return a builder for the harness-shape JSON envelope."""

    def _builder(
        tool: str,
        file_path: str,
        *,
        content: str | None = None,
        new_string: str | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "tool_name": tool,
            "tool_input": {"file_path": file_path},
        }
        tool_input = payload["tool_input"]
        assert isinstance(tool_input, dict)
        if content is not None:
            tool_input["content"] = content
        if new_string is not None:
            tool_input["new_string"] = new_string
        return json.dumps(payload)

    return _builder
