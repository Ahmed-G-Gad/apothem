# SPDX-License-Identifier: MIT

"""Self-tests for the diagram-staleness-grep validator.

Covers the fixture pair plus the C5 fence-recognition fix: indented
(list-nested) fences and `mermaid` info-strings carrying an init attribute
are now inspected, while a non-mermaid info-word (`mermaidx`, `python`) is
still ignored. `_today` is pinned so the stale/fresh boundary is
deterministic regardless of the calendar date the suite runs on.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "diagram_staleness_grep.py"
)
_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent
# A fixed reference date so age math is deterministic across calendar dates.
_PINNED_TODAY: Final[date] = date(2026, 7, 2)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("diagram_staleness_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["diagram_staleness_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_MOD, "_today", lambda: _PINNED_TODAY)


def _fence(opener: str, marker: str) -> str:
    return "\n".join(
        [
            "Some prose.",
            opener,
            "flowchart TD",
            marker,
            "    A --> B",
            "```",
            "More prose.",
        ]
    )


_FRESH: Final[str] = "%% verified: 2026-06-01 %%"
_STALE: Final[str] = "%% verified: 2025-01-01 %%"


def test_pass_fixture_passes() -> None:
    fixture = _FIXTURE_DIR / "pass.md"
    result = _MOD.check(fixture.read_text(encoding="utf-8"), fixture)
    assert result.passed, result.findings


def test_fail_fixture_is_flagged() -> None:
    fixture = _FIXTURE_DIR / "fail.md"
    result = _MOD.check(fixture.read_text(encoding="utf-8"), fixture)
    assert not result.passed


# --- column-0 fence (regression) -------------------------------------------


def test_column0_fresh_passes() -> None:
    assert _MOD.check(_fence("```mermaid", _FRESH)).passed


def test_column0_stale_is_flagged() -> None:
    assert not _MOD.check(_fence("```mermaid", _STALE)).passed


def test_column0_missing_marker_is_flagged() -> None:
    assert not _MOD.check(_fence("```mermaid", "no marker here")).passed


# --- C5: indented (list-nested) fences -------------------------------------


def test_indented_fence_fresh_passes() -> None:
    assert _MOD.check(_fence("   ```mermaid", _FRESH)).passed


def test_indented_fence_missing_marker_is_flagged() -> None:
    assert not _MOD.check(_fence("   ```mermaid", "no marker")).passed


# --- C5: init-attribute info-strings ---------------------------------------


def test_init_attribute_fence_fresh_passes() -> None:
    opener = '```mermaid {init: {"theme": "neutral"}}'
    assert _MOD.check(_fence(opener, _FRESH)).passed


def test_init_attribute_fence_missing_marker_is_flagged() -> None:
    opener = "```mermaid {init: {}}"
    assert not _MOD.check(_fence(opener, "no marker")).passed


# --- C5: non-mermaid info-words are not mermaid fences ----------------------


@pytest.mark.parametrize("opener", ["```mermaidx", "```python", "```md"])
def test_non_mermaid_fence_is_ignored(opener: str) -> None:
    # A missing marker inside a non-mermaid fence is not a mermaid finding.
    assert _MOD.check(_fence(opener, "no marker")).passed
