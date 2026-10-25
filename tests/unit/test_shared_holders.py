# SPDX-License-Identifier: MIT

"""Holders of a user-level folder, read from the install ledger.

A ``(harness, root)`` pair holds a user-level path while its current install
record lists the path. The ledger is the reference counter: an uninstall removes
a shared folder only when no other pair holds it, and anything it cannot prove
unheld stays.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from apothem.harnesses._shared.install_driver_shared import (
    HolderIndex,
    UserLevelGate,
    holder_index,
    path_key,
    retained_result,
)
from apothem.lib import install_ledger
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget
from apothem.lib.propagation import HarnessRules, InstallEntry, user_home

_SKILLS = InstallEntry(
    "skills/", "${USER_HOME}/.agents/skills/", "native_skills", "apothem-owned"
)


def _target(path: Path | str) -> LedgerTarget:
    return LedgerTarget(
        path=str(path),
        mode="native_skills",
        ownership_class="apothem-owned",
        outcome="created",
    )


def _install(harness: str, root: Path, *paths: Path | str) -> LedgerRecord:
    root.mkdir(parents=True, exist_ok=True)
    record = LedgerRecord.create(
        harness=harness,
        root=root,
        kind="install",
        targets=tuple(_target(path) for path in paths),
    )
    install_ledger.append_record(record)
    return record


def _end(kind: str, record: LedgerRecord) -> None:
    install_ledger.append_record(
        LedgerRecord.create(
            harness=record.harness,
            root=record.root,
            kind=kind,  # type: ignore[arg-type]
            install_id=record.install_id,
        )
    )


@pytest.fixture
def skill() -> Path:
    return user_home() / ".agents" / "skills" / "alpha"


def test_a_pair_holds_what_its_current_record_lists(
    tmp_path: Path, skill: Path
) -> None:
    _install("cursor", tmp_path / "a", skill)
    holders = holder_index().holders_of(skill)
    assert [(h.harness, h.root) for h in holders] == [("cursor", str(tmp_path / "a"))]


def test_nobody_holds_an_unlisted_path(tmp_path: Path, skill: Path) -> None:
    _install("cursor", tmp_path / "a", user_home() / "other")
    assert holder_index().holders_of(skill) == ()
    assert not holder_index().lists(skill)


def test_two_roots_of_one_harness_are_two_holders(tmp_path: Path, skill: Path) -> None:
    _install("cursor", tmp_path / "a", skill)
    _install("cursor", tmp_path / "b", skill)
    assert len(holder_index().holders_of(skill)) == 2


def test_exclude_leaves_out_only_the_asking_pair(tmp_path: Path, skill: Path) -> None:
    _install("cursor", tmp_path / "a", skill)
    _install("cursor", tmp_path / "b", skill)
    _install("zed", tmp_path / "a", skill)
    held = holder_index(exclude=("cursor", tmp_path / "a")).holders_of(skill)
    assert sorted((h.harness, h.root) for h in held) == [
        ("cursor", str(tmp_path / "b")),
        ("zed", str(tmp_path / "a")),
    ]


def test_an_uninstall_ends_the_claim(tmp_path: Path, skill: Path) -> None:
    record = _install("cursor", tmp_path / "a", skill)
    _end("uninstall", record)
    assert holder_index().holders_of(skill) == ()


def test_a_rollback_drops_the_install_and_the_ones_after_it(
    tmp_path: Path, skill: Path
) -> None:
    other = user_home() / ".agents" / "skills" / "beta"
    first = _install("cursor", tmp_path / "a", skill)
    second = _install("cursor", tmp_path / "a", skill, other)
    assert holder_index().holders_of(other)
    _end("rollback", second)
    assert holder_index().holders_of(other) == ()
    assert holder_index().holders_of(skill)
    _end("rollback", first)
    assert holder_index().holders_of(skill) == ()


def test_a_root_that_no_longer_exists_is_stale(tmp_path: Path, skill: Path) -> None:
    gone = tmp_path / "gone"
    _install("cursor", gone, skill)
    gone.rmdir()
    index = holder_index()
    assert index.holders_of(skill) == ()
    assert index.lists(skill)  # still evidence that Apothem wrote it
    assert [(h.harness, h.root) for h in index.stale] == [("cursor", str(gone))]


def test_dotdot_spellings_share_a_key(tmp_path: Path, skill: Path) -> None:
    # Codex records written before ${USER_HOME} name the folder through
    # <root>/.codex/..; the key folds it.
    legacy = user_home() / ".codex" / ".." / ".agents" / "skills" / "alpha"
    _install("codex", tmp_path / ".codex", legacy)
    assert holder_index().holders_of(skill)
    assert path_key(legacy) == path_key(skill)


@pytest.mark.skipif(os.name != "nt", reason="path case folds only on Windows")
def test_case_variants_share_a_key_on_windows(tmp_path: Path, skill: Path) -> None:
    _install("cursor", tmp_path / "a", str(skill).upper())
    assert holder_index().holders_of(skill)


def test_holder_labels_name_the_harness_and_root(tmp_path: Path, skill: Path) -> None:
    _install("cursor", tmp_path / "a", skill)
    _install("github_copilot", tmp_path / "b", skill)
    result = retained_result(skill, holder_index().holders_of(skill))
    assert result.outcome == "unchanged"
    assert result.operation == "shared_retained"
    assert f"cursor ({tmp_path / 'a'})" in result.message
    assert f"github-copilot ({tmp_path / 'b'})" in result.message


def _gate(root: Path) -> UserLevelGate:
    return UserLevelGate.build(
        HarnessRules(install=[_SKILLS], exclude=[], stale_sweep=[]),
        harness_name="cursor",
        root=root,
        harness_root=None,
        project_root=root,
    )


def test_the_gate_keeps_a_target_another_install_holds(
    tmp_path: Path, skill: Path
) -> None:
    mine = _install("cursor", tmp_path / "a", skill)
    _install("zed", tmp_path / "b", skill)
    removed: list[Path] = []
    results = _gate(tmp_path / "a").release(
        _SKILLS, mine, lambda target, allowed_root: removed.append(target)
    )
    assert removed == []
    assert [r.operation for r in results] == ["shared_retained"]


def test_the_gate_removes_the_target_of_the_last_holder(
    tmp_path: Path, skill: Path
) -> None:
    mine = _install("cursor", tmp_path / "a", skill)
    removed: list[Path] = []
    _gate(tmp_path / "a").release(
        _SKILLS, mine, lambda target, allowed_root: removed.append(target)
    )
    assert removed == [skill]


def test_a_record_that_lacks_the_path_removes_nothing(
    tmp_path: Path, skill: Path
) -> None:
    # A record from before the folder was managed, or none at all, must never
    # let an uninstall delete an operator's same-named folder.
    rules_only = _install("cursor", tmp_path / "a", tmp_path / "a" / ".cursor")
    removed: list[Path] = []
    gate = _gate(tmp_path / "a")
    assert (
        gate.release(_SKILLS, rules_only, lambda t, allowed_root: removed.append(t))
        == []
    )
    assert gate.release(_SKILLS, None, lambda t, allowed_root: removed.append(t)) == []
    assert removed == []


def test_an_unreadable_ledger_keeps_the_folder(tmp_path: Path, skill: Path) -> None:
    mine = _install("cursor", tmp_path / "a", skill)
    path = install_ledger.ledger_path("zed")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json\n{}\n", encoding="utf-8")
    removed: list[Path] = []
    results = _gate(tmp_path / "a").release(
        _SKILLS, mine, lambda target, allowed_root: removed.append(target)
    )
    assert removed == []
    assert [r.operation for r in results] == ["shared_retained"]
    assert "could not be read" in results[0].message
    with pytest.raises(install_ledger.LedgerError):
        holder_index()


def test_the_index_is_empty_without_any_ledger() -> None:
    assert holder_index() == HolderIndex()


def test_a_legacy_codex_record_is_released_through_its_dotdot_paths(
    tmp_path: Path, skill: Path
) -> None:
    # A record written before ${USER_HOME} lists Codex's skills as
    # <root>/.codex/../.agents/skills/x; uninstalling it still finds the folder.
    root = user_home() / ".codex"
    legacy = root / ".." / ".agents" / "skills" / "alpha"
    mine = _install("codex", root, legacy)
    removed: list[Path] = []
    gate = UserLevelGate.build(
        HarnessRules(install=[_SKILLS], exclude=[], stale_sweep=[]),
        harness_name="codex",
        root=root,
        harness_root=root,
        project_root=None,
    )
    results = gate.release(
        _SKILLS, mine, lambda target, allowed_root: removed.append(target)
    )
    assert results == []
    assert [path_key(p) for p in removed] == [path_key(skill)]
