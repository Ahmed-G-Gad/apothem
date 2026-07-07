# SPDX-License-Identifier: MIT

"""Integration tests for the ``apothem rollback`` CLI command.

Drives the command end-to-end through Click's runner: a real install (which
backs up the pre-existing operator anchor and writes a ledger record), then a
rollback that restores the recorded backup. Covers the success envelope, the
unknown-install-id structured error, and the conflicting-selector guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.harnesses.claude_code import ClaudeCodeAdapter
from apothem.lib import install_ledger
from apothem.schemas import profile_minimal_path

_OPERATOR_ANCHOR = "# Operator notes\n\nKeep me across install and rollback.\n"


def _install_with_backed_up_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Install claude-code over a pre-existing operator ``CLAUDE.md``.

    Redirects the adapter output path and the backup root into *tmp_path* (the
    ledger is isolated by the autouse conftest fixture). Returns the harness root
    and the anchor path. The pre-existing anchor forces a backup the rollback
    can later restore.
    """
    harness_root = tmp_path / ".claude"
    harness_root.mkdir(parents=True)
    settings = harness_root / "settings.json"
    anchor = harness_root / "CLAUDE.md"
    anchor.write_text(_OPERATOR_ANCHOR, encoding="utf-8")

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setattr(
        ClaudeCodeAdapter, "output_path", property(lambda self: settings)
    )
    profile = yaml.safe_load(profile_minimal_path().read_text(encoding="utf-8"))
    ClaudeCodeAdapter().install(profile)
    return harness_root, anchor


def test_rollback_last_restores_pre_install_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, anchor = _install_with_backed_up_anchor(tmp_path, monkeypatch)
    # Install folded the managed block into the operator anchor.
    assert anchor.read_text(encoding="utf-8") != _OPERATOR_ANCHOR
    # Drift the file further to prove rollback restores the recorded bytes.
    anchor.write_text("clobbered\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["rollback", "--harness", "claude-code", "--last", "--yes", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "success"
    assert envelope["command"] == "rollback"
    assert envelope["error"] is None
    assert any(r["operation"] == "rollback" for r in envelope["results"])
    # The operator's pre-install anchor is restored byte-for-byte.
    assert anchor.read_text(encoding="utf-8") == _OPERATOR_ANCHOR


def test_rollback_unknown_install_id_is_structured_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_with_backed_up_anchor(tmp_path, monkeypatch)
    result = CliRunner().invoke(
        main,
        [
            "rollback",
            "--harness",
            "claude-code",
            "--install-id",
            "01BOGUSULIDDOESNOTEXIST00",
            "--format",
            "json",
            # JSON mode cannot prompt, so --yes is required to get past the
            # up-front confirmation gate to the no-record path under test.
            "--yes",
        ],
    )
    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "rollback.no_record"
    # A structured envelope, never a bare traceback.
    assert "Traceback" not in result.output


def test_rollback_corrupted_ledger_is_structured_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_with_backed_up_anchor(tmp_path, monkeypatch)
    # Corrupt the ledger mid-file: garbage BEFORE the valid install record is
    # not a torn final append, so the reader raises LedgerError.
    ledgers = list(install_ledger.STATE_ROOT.rglob(install_ledger.LEDGER_FILENAME))
    assert ledgers, "install should have written a ledger record"
    ledger = ledgers[0]
    ledger.write_text(
        "corrupt garbage line\n" + ledger.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        ["rollback", "--harness", "claude-code", "--last", "--yes", "--format", "json"],
    )

    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "rollback.ledger_corrupt"
    # A structured envelope, never a bare traceback.
    assert "Traceback" not in result.output


def test_rollback_conflicting_selectors_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_with_backed_up_anchor(tmp_path, monkeypatch)
    result = CliRunner().invoke(
        main,
        [
            "rollback",
            "--harness",
            "claude-code",
            "--last",
            "--install-id",
            "01SOMEULID0000000000000000",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["error"]["code"] == "rollback.conflicting_selectors"
