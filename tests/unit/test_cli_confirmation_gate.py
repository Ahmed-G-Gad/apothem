# SPDX-License-Identifier: MIT

"""Destructive-confirmation gate for ``uninstall`` / ``rollback``.

JSON mode must never mix prompt text into the single JSON document, and a
non-interactive run has no terminal to answer a prompt: without ``--yes``
both commands refuse up front with the structured ``confirmation_required``
error instead of dying mid-batch on a bare Abort. Interactive plain runs
keep the per-target prompt.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from apothem.cli import main


def test_uninstall_json_without_yes_refuses_with_envelope(
    runner: CliRunner, mock_adapter: MagicMock
) -> None:
    with patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter):
        result = runner.invoke(main, ["uninstall", "--harness", "codex", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output.strip())
    assert data["status"] == "error"
    assert data["error"]["code"] == "uninstall.confirmation_required"
    mock_adapter.uninstall.assert_not_called()


def test_uninstall_plain_non_interactive_without_yes_refuses(
    runner: CliRunner, mock_adapter: MagicMock
) -> None:
    with (
        patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter),
        patch("apothem.cli._stdin_is_interactive", return_value=False),
    ):
        result = runner.invoke(main, ["uninstall", "--harness", "codex"])
    assert result.exit_code == 1
    assert "--yes" in result.output
    mock_adapter.uninstall.assert_not_called()


def test_uninstall_plain_interactive_still_prompts(
    runner: CliRunner, mock_adapter: MagicMock
) -> None:
    with (
        patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter),
        patch("apothem.cli._stdin_is_interactive", return_value=True),
    ):
        result = runner.invoke(main, ["uninstall", "--harness", "codex"], input="y\n")
    assert result.exit_code == 0, result.output
    assert "Remove" in result.output
    mock_adapter.uninstall.assert_called_once()


def test_uninstall_plain_interactive_decline_aborts(
    runner: CliRunner, mock_adapter: MagicMock
) -> None:
    with (
        patch("apothem.cli._load_adapter_for_entry", return_value=mock_adapter),
        patch("apothem.cli._stdin_is_interactive", return_value=True),
    ):
        result = runner.invoke(main, ["uninstall", "--harness", "codex"], input="n\n")
    assert result.exit_code != 0
    mock_adapter.uninstall.assert_not_called()


def test_rollback_json_without_yes_refuses_with_envelope(runner: CliRunner) -> None:
    result = runner.invoke(main, ["rollback", "--harness", "claude-code", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output.strip())
    assert data["status"] == "error"
    assert data["error"]["code"] == "rollback.confirmation_required"


def test_rollback_plain_non_interactive_without_yes_refuses(
    runner: CliRunner,
) -> None:
    with patch("apothem.cli._stdin_is_interactive", return_value=False):
        result = runner.invoke(main, ["rollback", "--harness", "claude-code"])
    assert result.exit_code == 1
    assert "--yes" in result.output
