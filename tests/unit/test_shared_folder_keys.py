# SPDX-License-Identifier: MIT

"""Shared user-level folders are counted by the folder, not by its spelling.

The install ledger counts which installs use ``~/.agents/skills/`` and
``~/.config/apothem/``. When the home folder is a link (``/home`` leading to
``/var/home``, a Windows profile moved behind a junction), one install can
record the home spelled through the link and another the folder it leads to.
Both name the same folders, so an uninstall of one must keep them for the
other. Each test makes a real link: a symbolic link, or a junction where
symbolic links need a privilege the host lacks; it is skipped when neither
can be made.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.cli._user_level_report import ledger_holders
from apothem.harnesses._shared.install_driver_shared import holder_index, path_key
from apothem.lib import clean_slate, install_ledger
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget
from apothem.lib.propagation import user_home

_SHARED = (
    Path(".agents", "skills"),
    Path(".config", "apothem", "rules"),
    Path(".config", "apothem", "templates"),
)


def _link(link: Path, target: Path) -> None:
    """Make *link* lead to the folder *target*, or skip the test when no link can be made."""
    if not target.is_dir():
        target.mkdir(parents=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot make a symbolic link")
    try:
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    except OSError:
        pytest.skip("this host can make neither a symbolic link nor a junction")


def _spell_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def _files(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*"))


def _record(harness: str, root: Path, *paths: Path | str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    install_ledger.append_record(
        LedgerRecord.create(
            harness=harness,
            root=root,
            kind="install",
            targets=tuple(
                LedgerTarget(
                    path=str(path),
                    mode="native_skills",
                    ownership_class="apothem-owned",
                    outcome="created",
                )
                for path in paths
            ),
        )
    )


@pytest.fixture
def homes(tmp_path: Path) -> tuple[Path, Path]:
    """Return ``(real home, link to it)``."""
    real = tmp_path / "real-home"
    linked = tmp_path / "link-home"
    _link(linked, real)
    return real, linked


def _install_under_two_spellings(
    real: Path, linked: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Install Codex through the link and Windsurf through the real home.

    Returns the second install's JSON output.
    """
    runner = CliRunner()
    _spell_home(monkeypatch, linked)
    result = runner.invoke(main, ["install", "--harness", "codex", "--yes"])
    assert result.exit_code == 0, result.output
    _spell_home(monkeypatch, real)
    project.mkdir()
    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "windsurf",
            "--project",
            str(project),
            "--yes",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output


def _shared_notes(output: str) -> list[dict[str, object]]:
    """Return the ``shared_root`` notes anywhere in a command's JSON *output*."""
    found: list[dict[str, object]] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("operation") == "shared_root":
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(output))
    return found


def test_an_uninstall_keeps_folders_an_install_under_the_other_spelling_uses(
    homes: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real, linked = homes
    project = tmp_path / "project"
    _install_under_two_spellings(real, linked, project, monkeypatch)
    before = {folder: _files(real / folder) for folder in _SHARED}
    assert all(before.values())

    _spell_home(monkeypatch, linked)
    result = CliRunner().invoke(
        main, ["uninstall", "--harness", "codex", "--yes", "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    assert {folder: _files(real / folder) for folder in _SHARED} == before
    notes = [
        entry
        for entry in json.loads(result.output)["warnings"]
        if entry.get("operation") == "shared_root"
    ]
    assert {Path(note["path"]).relative_to(linked) for note in notes} == set(_SHARED)
    for note in notes:
        assert note["role"] == "retained", note["message"]
        assert note["kept"] == note["total"]
        assert note["holders"] == [f"windsurf ({project})"]
        assert f"still used by windsurf ({project})" in note["message"]


def test_the_install_note_counts_installs_under_both_spellings(
    homes: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real, linked = homes
    output = _install_under_two_spellings(
        real, linked, tmp_path / "project", monkeypatch
    )

    skills = [
        note
        for note in _shared_notes(output)
        if Path(str(note["path"])) == real / ".agents" / "skills"
    ]
    assert skills, output
    for note in skills:
        assert note["holders"] == ["codex", "windsurf"], note
        assert "Installs using it now: Codex, Windsurf." in str(note["message"])
    for home in (linked, real):
        _spell_home(monkeypatch, home)
        holders = ledger_holders()
        assert holders is not None
        assert sorted(holders(home / ".agents" / "skills")) == ["codex", "windsurf"]


def test_holders_under_two_spellings_share_one_key(
    homes: tuple[Path, Path], tmp_path: Path
) -> None:
    real, linked = homes
    through_link = linked / ".agents" / "skills" / "alpha"
    direct = real / ".agents" / "skills" / "alpha"
    _record("codex", tmp_path / "a", through_link)
    _record("cursor", tmp_path / "b", direct)

    index = holder_index(exclude=("codex", tmp_path / "a"))

    assert path_key(through_link) == path_key(direct)
    assert [h.harness for h in index.holders_of(through_link)] == ["cursor"]
    assert index.lists(direct)


def test_the_exclude_matches_the_root_as_spelled(
    homes: tuple[Path, Path],
) -> None:
    # The ledger finds an install's records by the root as spelled, so a
    # record of the same harness under the other spelling is one the
    # uninstall cannot reach: it still holds what it lists.
    real, linked = homes
    skill = real / ".agents" / "skills" / "alpha"
    _record("codex", real / ".codex", skill)

    other = holder_index(exclude=("codex", linked / ".codex"))
    own = holder_index(exclude=("codex", real / ".codex"))

    through_link = linked / ".agents" / "skills" / "alpha"
    assert [h.harness for h in other.holders_of(through_link)] == ["codex"]
    assert not own.holders_of(skill)


def _install_codex_under_both_spellings(
    real: Path, linked: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Install Codex with the home spelled as the real folder, then through the link."""
    runner = CliRunner()
    for home in (real, linked):
        _spell_home(monkeypatch, home)
        result = runner.invoke(main, ["install", "--harness", "codex", "--yes"])
        assert result.exit_code == 0, result.output


def test_a_rollback_keeps_folders_the_same_tool_holds_under_the_other_spelling(
    homes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    real, linked = homes
    _install_codex_under_both_spellings(real, linked, monkeypatch)
    before = {folder: _files(real / folder) for folder in _SHARED}
    assert all(before.values())

    _spell_home(monkeypatch, linked)
    result = CliRunner().invoke(main, ["rollback", "--harness", "codex", "--yes"])

    assert result.exit_code == 0, result.output
    assert {folder: _files(real / folder) for folder in _SHARED} == before
    _spell_home(monkeypatch, real)
    verified = CliRunner().invoke(main, ["verify", "--harness", "codex"])
    assert verified.exit_code == 0, verified.output


def test_the_uninstall_note_matches_what_the_uninstall_does(
    homes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    real, linked = homes
    _install_codex_under_both_spellings(real, linked, monkeypatch)
    before = {folder: _files(real / folder) for folder in _SHARED}

    _spell_home(monkeypatch, linked)
    result = CliRunner().invoke(
        main, ["uninstall", "--harness", "codex", "--yes", "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    notes = _shared_notes(result.output)
    folders = {Path(str(note["path"])).relative_to(linked) for note in notes}
    assert folders == set(_SHARED)
    for note in notes:
        folder = Path(str(note["path"])).relative_to(linked)
        # The record under the real spelling is another install the ledger
        # still lists, so the note says kept and the files are there.
        assert note["role"] == "retained", note["message"]
        assert note["kept"] == note["total"]
        assert note["holders"] == [f"codex ({real / '.codex'})"]
        assert _files(real / folder) == before[folder]


def test_a_legacy_codex_record_still_folds_when_codex_is_a_link(
    tmp_path: Path,
) -> None:
    # Records written before ${USER_HOME} spell the skills through ~/.codex/..;
    # the spelling is folded before any link is followed, so a linked ~/.codex
    # does not move the key to the folder beside where the link leads.
    home = user_home()
    _link(home / ".codex", tmp_path / "elsewhere" / "deep" / "codex")
    skill = home / ".agents" / "skills" / "alpha"
    legacy = f"{home / '.codex'}{os.sep}..{os.sep}.agents{os.sep}skills{os.sep}alpha"
    _record("codex", home / ".codex", legacy)

    assert path_key(legacy) == path_key(skill)
    assert [h.harness for h in holder_index().holders_of(skill)] == ["codex"]


def test_a_target_that_is_itself_a_link_is_keyed_as_the_entry(
    tmp_path: Path,
) -> None:
    skills = user_home() / ".agents" / "skills"
    elsewhere = tmp_path / "elsewhere" / "alpha"
    entry = skills / "alpha"
    _link(entry, elsewhere)
    _record("cursor", tmp_path / "a", entry)

    assert path_key(entry) != path_key(elsewhere)
    assert path_key(entry).endswith(os.path.normcase(f"skills{os.sep}alpha"))
    index = holder_index()
    assert index.holders_of(entry)
    assert not index.holders_of(elsewhere)


def test_a_memo_resolves_each_folder_once(tmp_path: Path) -> None:
    folder = tmp_path / ".agents" / "skills"
    memo: dict[str, str] = {}

    keys = [path_key(folder / name, memo) for name in ("a", "b", "c")]

    assert list(memo) == [os.path.normpath(str(folder))]
    assert keys == [path_key(folder / name) for name in ("a", "b", "c")]


def test_only_a_path_in_a_user_level_folder_is_resolved(
    homes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Project files are never looked up as shared, so they cost no
    # filesystem call: they keep the key of their spelling.
    real, linked = homes
    project_file = linked / "project" / ".windsurf" / "rules" / "a.md"
    resolved: list[str] = []
    realpath = os.path.realpath

    def counted(path: str) -> str:
        resolved.append(path)
        return realpath(path)

    monkeypatch.setattr(os.path, "realpath", counted)

    assert path_key(project_file) == os.path.normcase(str(project_file))
    assert path_key(linked / ".agents") == os.path.normcase(str(linked / ".agents"))
    assert not resolved
    for prefix in _SHARED:
        assert path_key(linked / prefix) == path_key(real / prefix)
        assert path_key(linked / prefix / "x") == path_key(real / prefix / "x")


# --- clean slate ---------------------------------------------------------------


def _forbid_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any backup or removal fail the test, so no run reaches a real root."""

    def refuse(*_args: object, **_kwargs: object) -> object:
        pytest.fail("clean slate went past its home check")

    monkeypatch.setattr(clean_slate, "_backup_targets", refuse)
    monkeypatch.setattr(clean_slate, "_remove_path", refuse)


def test_clean_slate_refuses_a_home_that_is_a_link_to_a_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The real link is followed, but it leads to a folder in tmp_path that
    # stands for the root: a link to a real root left behind by a killed run
    # would lead whatever cleans the temp folder there.
    _forbid_changes(monkeypatch)
    home = tmp_path / "home"
    stand_in = tmp_path / "drive-root"
    _link(home, stand_in)
    stand_in_resolved = stand_in.resolve()
    real_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        found = real_resolve(self, strict)
        return Path(found.anchor) if found == stand_in_resolved else found

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(clean_slate.UnsafeHomeError, match="leads to"):
        clean_slate.run_clean_slate(
            home, assume_yes=True, backup_root=tmp_path / "backups"
        )


def test_clean_slate_refuses_a_home_that_resolves_to_a_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Without a real link: the home's resolution alone decides.
    _forbid_changes(monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    real_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        return Path(self.anchor) if self == home else real_resolve(self, strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(clean_slate.UnsafeHomeError, match="leads to"):
        clean_slate.run_clean_slate(
            home, assume_yes=True, backup_root=tmp_path / "backups"
        )


def test_clean_slate_refuses_a_home_whose_links_cannot_be_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_changes(monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    real_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        if self == home:
            raise RuntimeError("Symlink loop")
        return real_resolve(self, strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(clean_slate.UnsafeHomeError, match="cannot be followed"):
        clean_slate.run_clean_slate(home, dry_run=True)
