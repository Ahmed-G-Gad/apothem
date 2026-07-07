# SPDX-License-Identifier: MIT

"""Unit pins for the preview label + status helpers (operation_label / preview_status).

These guard the plain-language vocabulary the ``diff`` preview renders: every
install-entry mode has an explicit human label (no internal token leaks), an
unknown kind humanizes rather than exposing snake_case, and the dry-run status
translation reads coherently ("would write", never the contradictory "skipped").
"""

from __future__ import annotations

import pytest

from apothem.harnesses._shared.install_driver import (
    OPERATION_LABELS,
    operation_label,
    preview_status,
)
from apothem.harnesses._shared.install_driver_types import _INSTALL_ENTRY_MODES


def test_every_install_entry_mode_has_an_explicit_label() -> None:
    """A newly-added install mode must gain a label in the same edit, not silently
    fall through to the humanized fallback."""
    missing = [mode for mode in _INSTALL_ENTRY_MODES if mode not in OPERATION_LABELS]
    assert not missing, f"install entry modes without an explicit label: {missing}"


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("write_text", "Write file"),
        ("sentinel_merge", "Merge into file"),
        ("merge_tree_entries", "Merge directory"),
        ("command_skills", "Install skills"),
        ("codex_agents", "Install agents"),
        ("gemini_commands", "Install commands"),
        ("sweep_stale", "Prune stale files"),
        ("capability_projection", "Project capability"),
    ],
)
def test_operation_label_known_kinds(operation: str, expected: str) -> None:
    assert operation_label(operation) == expected


def test_operation_label_humanizes_unknown_kind() -> None:
    label = operation_label("some_future_mode")
    assert label == "Some future mode"
    assert "_" not in label


def test_operation_label_empty_is_safe() -> None:
    assert operation_label("") == ""


@pytest.mark.parametrize(
    ("operation", "outcome", "expected"),
    [
        ("write_text", "skipped", "would write"),
        ("merge_tree_entries", "skipped", "would write"),
        ("command_skills", "skipped", "would write"),
        ("sweep_stale", "skipped", "would remove"),
        ("sweep_stale", "unchanged", "no change"),
        ("write_text", "unchanged", "no change"),
        ("write_text", "created", "would create"),
        ("write_text", "updated", "would update"),
        ("write_text", "error", "error"),
        ("capability_projection", "warning", "warning"),
    ],
)
def test_preview_status_dry_run(operation: str, outcome: str, expected: str) -> None:
    assert preview_status(operation, outcome, dry_run=True) == expected


@pytest.mark.parametrize(
    "outcome", ["created", "updated", "unchanged", "skipped", "error"]
)
def test_preview_status_real_run_passes_outcome_through(outcome: str) -> None:
    """Outside a dry run the raw outcome is already coherent — return it verbatim."""
    assert preview_status("write_text", outcome, dry_run=False) == outcome
