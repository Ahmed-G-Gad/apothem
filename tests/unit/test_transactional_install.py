# SPDX-License-Identifier: MIT

"""Transactional install — per-(harness, root) lock + compensating rollback.

Covers the lock keying and serialization, the compensating-rollback primitive,
and a mid-pass failure-injection that leaves the operator's prior state intact
while releasing the lock for a later install.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationResult
from apothem.lib import atomic_io, install_ledger


def test_install_lock_path_is_keyed_by_harness_and_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_ledger, "STATE_ROOT", tmp_path / "state")
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    lock_a = install_driver._install_lock_path("claude_code", root_a)
    assert lock_a == install_driver._install_lock_path("claude_code", root_a)
    assert lock_a != install_driver._install_lock_path("claude_code", root_b)
    assert lock_a != install_driver._install_lock_path("codex", root_a)


def test_same_root_serializes_while_other_root_is_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_ledger, "STATE_ROOT", tmp_path / "state")
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    lock_a = install_driver._install_lock_path("claude_code", root_a)
    lock_b = install_driver._install_lock_path("claude_code", root_b)

    order: list[str] = []
    holding_a = threading.Event()
    release_a = threading.Event()

    def hold_a() -> None:
        with atomic_io.advisory_lock(lock_a):
            order.append("a-enter")
            holding_a.set()
            release_a.wait(5)
            order.append("a-exit")

    holder = threading.Thread(target=hold_a)
    holder.start()
    assert holding_a.wait(5)

    # A different root must NOT be blocked while root A's lock is held.
    b_acquired = threading.Event()

    def grab_b() -> None:
        with atomic_io.advisory_lock(lock_b, timeout=5):
            b_acquired.set()

    tb = threading.Thread(target=grab_b)
    tb.start()
    assert b_acquired.wait(5), "a different root must not be blocked"
    tb.join(5)

    # A second acquirer of the SAME root blocks until A releases.
    def grab_a_again() -> None:
        with atomic_io.advisory_lock(lock_a, timeout=5):
            order.append("a2-enter")

    ta2 = threading.Thread(target=grab_a_again)
    ta2.start()
    # A blocked acquirer cannot complete: join must time out with the thread
    # still alive. This is deterministic — were the lock NOT blocking, ta2
    # would acquire, append "a2-enter", and finish, so the join would return
    # and is_alive() would be False.
    ta2.join(1)
    assert ta2.is_alive(), "second same-root acquirer should still be blocked"
    assert order == ["a-enter"], "second same-root acquirer should still be blocked"

    release_a.set()
    holder.join(5)
    ta2.join(5)
    assert order == ["a-enter", "a-exit", "a2-enter"]  # strictly serialized


def test_compensating_rollback_restores_backed_up_and_removes_fresh(
    tmp_path: Path,
) -> None:
    allowed_root = tmp_path
    # A target that pre-existed: backed up, then clobbered — must be restored.
    backed = tmp_path / "kept.txt"
    backed.write_text("CLOBBERED\n", encoding="utf-8")
    backup = tmp_path / "bk" / "kept.txt"
    backup.parent.mkdir()
    backup.write_text("ORIGINAL\n", encoding="utf-8")
    # A target created fresh this pass: no backup — must be removed.
    fresh = tmp_path / "fresh.txt"
    fresh.write_text("new\n", encoding="utf-8")
    # An unchanged result: must be left untouched.
    keep = tmp_path / "keep.txt"
    keep.write_text("stays\n", encoding="utf-8")
    # A target outside the allowed root: must be skipped defensively.
    outside_dir = tmp_path.parent / "outside-root"
    outside_dir.mkdir(exist_ok=True)
    outside = outside_dir / "external.txt"
    outside.write_text("external\n", encoding="utf-8")

    results = [
        MaterializationResult(
            "updated", "write_bytes", str(backed), "x", backup_path=str(backup)
        ),
        MaterializationResult("created", "write_bytes", str(fresh), "x"),
        MaterializationResult("unchanged", "write_bytes", str(keep), "x"),
        MaterializationResult("created", "write_bytes", str(outside), "x"),
    ]
    install_driver._compensating_rollback(results, allowed_root=allowed_root)

    assert backed.read_text(encoding="utf-8") == "ORIGINAL\n"  # restored
    assert not fresh.exists()  # removed (was newly created)
    assert keep.read_text(encoding="utf-8") == "stays\n"  # untouched
    assert outside.exists()  # outside the boundary, never touched
    outside.unlink()


def test_failed_install_rolls_back_and_releases_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    harness_root = tmp_path / ".claude"

    original = install_driver._dispatch_install_entry
    state = {"calls": 0}
    created_paths: list[str] = []

    def failing(*args: object, **kwargs: object) -> list[MaterializationResult]:
        state["calls"] += 1
        if state["calls"] == 2:
            raise OSError("injected mid-pass failure")
        entry_results = original(*args, **kwargs)  # type: ignore[arg-type]
        created_paths.extend(
            r.path for r in entry_results if r.outcome in {"created", "updated"}
        )
        return entry_results

    monkeypatch.setattr(install_driver, "_dispatch_install_entry", failing)
    with pytest.raises(OSError, match="injected mid-pass failure"):
        install_driver.run_install("claude_code", harness_root=harness_root)

    # Everything the first entry wrote (clean root → no backups) is rolled back.
    assert created_paths, "the first entry should have written at least one target"
    for path in created_paths:
        assert not Path(path).exists(), f"partial install left {path} behind"

    # The lock was released on the exception: a clean re-install now succeeds.
    monkeypatch.setattr(install_driver, "_dispatch_install_entry", original)
    run = install_driver.run_install("claude_code", harness_root=harness_root)
    assert run.changed
    assert not run.errors
