# SPDX-License-Identifier: MIT

"""Out-of-root backup keying + restore round-trip.

A user-scope harness whose targets reach outside its own root (codex writes
``~/.agents/skills/…`` and ``~/.config/apothem/…`` alongside ``~/.codex/…``) must
key each backup by its path relative to the allowed-write boundary (the parent),
not the harness root — otherwise two distinct out-of-root files collapse to one
basename and restore lands in the wrong place.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver


def _backup_timestamps(backup_root: Path, *backups: Path) -> list[str]:
    return sorted({backup.relative_to(backup_root).parts[0] for backup in backups})


def test_out_of_root_targets_keep_full_path_and_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    # Pin the backup timestamp: `_timestamp_slug` has only second granularity,
    # so a real run that straddles a second boundary keys foo and bar under two
    # timestamp directories and the restore round-trip turns order-sensitive (an
    # observed intermittent failure on the Windows py3.10 leg). Pinning forces
    # the HARDER same-directory case — distinct boundary-relative paths under one
    # timestamp — which is exactly the full-path-keying invariant under test.
    monkeypatch.setattr(install_driver, "_timestamp_slug", lambda: "20260101T000000Z")

    harness_root = tmp_path / ".codex"  # user-scope install root
    harness_root.mkdir()
    # Two distinct out-of-root targets that share a basename.
    foo = tmp_path / ".agents" / "skills" / "foo" / "SKILL.md"
    bar = tmp_path / ".agents" / "skills" / "bar" / "SKILL.md"
    foo.parent.mkdir(parents=True)
    bar.parent.mkdir(parents=True)
    foo.write_text("foo original\n", encoding="utf-8")
    bar.write_text("bar original\n", encoding="utf-8")

    # allowed_root is the boundary the install path computes (harness_root.parent).
    allowed_root = tmp_path
    foo_backup = install_driver.backup_existing(
        foo, install_root=harness_root, harness_name="codex", allowed_root=allowed_root
    )
    bar_backup = install_driver.backup_existing(
        bar, install_root=harness_root, harness_name="codex", allowed_root=allowed_root
    )
    assert foo_backup is not None
    assert bar_backup is not None
    # Distinct backups keyed by the full boundary-relative path — NOT one basename.
    assert foo_backup != bar_backup
    assert "foo" in foo_backup.parts
    assert "bar" in bar_backup.parts

    # Drift both, then restore from the captured timestamp set(s).
    foo.write_text("foo clobbered\n", encoding="utf-8")
    bar.write_text("bar clobbered\n", encoding="utf-8")
    results = []
    for timestamp in _backup_timestamps(backup_root, foo_backup, bar_backup):
        results.extend(
            install_driver.restore_backup("codex", timestamp, harness_root=harness_root)
        )
    assert all(result.outcome != "error" for result in results)

    # Restored to their TRUE out-of-root locations, not collapsed under ~/.codex/.
    assert foo.read_text(encoding="utf-8") == "foo original\n"
    assert bar.read_text(encoding="utf-8") == "bar original\n"
    assert not (harness_root / "SKILL.md").exists()


def test_in_root_target_round_trips_through_boundary_keying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    harness_root = tmp_path / ".codex"
    harness_root.mkdir()
    target = harness_root / "AGENTS.md"
    target.write_text("operator agents\n", encoding="utf-8")

    backup = install_driver.backup_existing(
        target,
        install_root=harness_root,
        harness_name="codex",
        allowed_root=tmp_path,
    )
    assert backup is not None
    # Keyed under the harness dir relative to the boundary (".codex/AGENTS.md").
    assert ".codex" in backup.parts

    target.write_text("clobbered\n", encoding="utf-8")
    timestamp = backup.relative_to(backup_root).parts[0]
    install_driver.restore_backup("codex", timestamp, harness_root=harness_root)
    assert target.read_text(encoding="utf-8") == "operator agents\n"
