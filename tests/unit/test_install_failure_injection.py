# SPDX-License-Identifier: MIT

"""Failure-injection tests for `install_driver.run_install`.

These are deterministic unit tests (not property-based). They exercise the
documented transactional contract of `run_install`:

* The mutating pass runs under an advisory lock; on a mid-pass write failure
  `run_install` surfaces a clean `MaterializationError` (not a bare unhandled
  traceback) and `_compensating_rollback` restores prior on-disk state.
* `write_bytes_safely` catches `OSError` from the low-level atomic write and
  converts it into an `error`-outcome result; an `error` result on any install
  entry makes `run_install` raise `MaterializationError`.

The autouse install-ledger isolation from `tests/unit/conftest.py` redirects the
ledger to a per-test directory. `BACKUP_ROOT` is redirected per-test so backups
land under `tmp_path`, mirroring the existing transactional-install tests.

`claude_code` is the install subject: a user-scope (harness_root) adapter whose
first install entry writes `settings.json` (operator-owned, JSON write_text) and
whose later entries write multiple tree files - a multi-entry manifest where a
mid-pass failure is partway through the pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationError


@pytest.fixture(autouse=True)
def _redirect_backup_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Send backup copies under tmp_path so no real ~/.apothem/backups write."""
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")


def _operator_settings() -> str:
    """Return operator-authored settings.json content with a custom key."""
    return json.dumps({"operatorKey": "operator-value"}, indent=2) + "\n"


def test_mid_install_write_failure_rolls_back_and_surfaces_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An Nth-call write OSError yields a clean error and restores prior state.

    Contract: the low-level atomic write raises OSError partway through the
    multi-entry manifest. `write_bytes_safely` catches it -> `error` result ->
    `run_install` raises `MaterializationError`. `_compensating_rollback`
    restores the pre-seeded operator settings.json from its backup, and no
    half-installed apothem tree residue remains.
    """
    harness_root = tmp_path / ".claude"
    harness_root.mkdir()
    settings = harness_root / "settings.json"
    settings.write_text(_operator_settings(), encoding="utf-8")

    real_write = install_driver._write_file_atomically
    state = {"calls": 0}

    def failing_write(target: Path, data: bytes) -> None:
        state["calls"] += 1
        # Call 1 is settings.json (the first install entry). Every later write
        # (the tree-merge files) fails, so the failure is partway through the
        # pass and no apothem tree file is ever written.
        if state["calls"] == 1:
            real_write(target, data)
            return
        raise OSError("injected mid-install write failure")

    monkeypatch.setattr(install_driver, "_write_file_atomically", failing_write)

    with pytest.raises(MaterializationError) as exc_info:
        install_driver.run_install("claude_code", harness_root=harness_root)

    # The surfaced failure is the documented MaterializationError, not a bare
    # OSError traceback escaping run_install.
    assert "write failed" in str(exc_info.value)
    assert state["calls"] >= 2, "the failure must fire after the first write"

    # The pre-seeded operator file is restored to its original bytes by rollback.
    assert settings.exists(), "rollback should restore the operator settings file"
    restored = json.loads(settings.read_text(encoding="utf-8"))
    assert restored.get("operatorKey") == "operator-value"

    # No half-installed apothem tree residue: the agents/ tree (the second
    # install entry) has no files written by the failed pass.
    agents_dir = harness_root / "agents"
    if agents_dir.exists():
        assert not any(agents_dir.rglob("*.md")), "partial agents/ install left behind"


def test_unwritable_target_yields_clean_error_not_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write into an unwritable target yields a clean MaterializationError.

    Simulated cross-platform via a monkeypatched write raising PermissionError
    (real read-only chmod is unreliable on Windows). The first write fails, so
    `write_bytes_safely` records an `error` result and `run_install` raises
    `MaterializationError` rather than letting the PermissionError escape as an
    unhandled traceback. A fresh root has no prior state to restore.
    """
    harness_root = tmp_path / ".claude"

    def unwritable(target: Path, data: bytes) -> None:
        raise PermissionError("injected read-only target")

    monkeypatch.setattr(install_driver, "_write_file_atomically", unwritable)

    with pytest.raises(MaterializationError) as exc_info:
        install_driver.run_install("claude_code", harness_root=harness_root)

    assert "write failed" in str(exc_info.value)
    # The run carried on the error has at least one error-outcome result.
    assert exc_info.value.run.errors, "the failed run should carry an error result"

    # No partial apothem install residue under a fresh root.
    settings = harness_root / "settings.json"
    assert not settings.exists(), "the failed settings.json write left a partial file"
