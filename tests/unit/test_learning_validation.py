# SPDX-License-Identifier: MIT

"""Unit tests for learning validation + signal-store edge branches.

The main learning suite exercises capture -> extract -> promote end to end;
these target the validation error paths and store edges directly: validate_signal
on an invalid mapping, _validate_skill_frontmatter on invalid frontmatter, and
LearningStore.signals on blank lines (skipped) and a non-object JSON line
(rejected).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.lib import learning as lrn
from apothem.lib.data_home import resolve_shared_data_home


def _store(tmp_path: Path) -> lrn.LearningStore:
    return lrn.LearningStore(resolve_shared_data_home(base=tmp_path).ensure())


def test_validate_signal_rejects_invalid_mapping() -> None:
    with pytest.raises(lrn.LearningError, match="invalid learning signal"):
        lrn.validate_signal({})  # missing every required field


def test_validate_skill_frontmatter_rejects_invalid() -> None:
    with pytest.raises(lrn.LearningError, match="invalid promoted skill frontmatter"):
        lrn._validate_skill_frontmatter({})  # missing required name / description


def test_signals_skips_blank_lines(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store._signals_path.write_text("\n  \n", encoding="utf-8")  # only blank lines
    assert store.signals() == []  # blank lines are skipped, not parsed


def test_signals_rejects_non_object_line(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store._signals_path.write_text("[1, 2, 3]\n", encoding="utf-8")  # a JSON array
    with pytest.raises(lrn.LearningError, match="must be a JSON object"):
        store.signals()
