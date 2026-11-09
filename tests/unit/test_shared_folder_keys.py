# SPDX-License-Identifier: MIT

"""Shared user-level folders are counted by the folder, not by its spelling.

The install ledger counts which installs use ``~/.agents/skills/`` and
``~/.config/apothem/``. When the home folder is a link (``/home`` leading to
``/var/home``, a Windows profile moved behind a junction), one install can
record the home spelled through the link and another the folder it leads to.
Both name the same folders, so an uninstall of one must keep them for the
other. One tool recorded under both spellings is one install to an
uninstall, which removes what either record shows Apothem wrote, and a
rollback undoes only the record it is run under. A rollback also removes a
shared folder its install found in place when an install that has let go of
it made it, unless something removed it since. Each test
that needs a link makes a real one: a symbolic link, or a junction where
symbolic links need a privilege the host lacks; it is skipped when neither
can be made.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.cli._user_level_report import LedgerView, ledger_holders
from apothem.harnesses._shared import install_driver_keys
from apothem.harnesses._shared.install_driver_shared import holder_index, path_key
from apothem.lib import install_ledger
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
    # The ledger finds an install's records by the root's exact text, so a
    # record of the same harness under the other spelling stays a holder
    # unless the caller names that spelling too, as an uninstall does.
    real, linked = homes
    skill = real / ".agents" / "skills" / "alpha"
    _record("codex", real / ".codex", skill)

    other = holder_index(exclude=("codex", linked / ".codex"))
    own = holder_index(exclude=("codex", real / ".codex"))
    both = holder_index(
        exclude=("codex", linked / ".codex"), also=(str(real / ".codex"),)
    )

    through_link = linked / ".agents" / "skills" / "alpha"
    assert [h.harness for h in other.holders_of(through_link)] == ["codex"]
    assert not own.holders_of(skill)
    assert not both.holders_of(through_link)


def test_the_exclude_never_folds_the_case_of_the_root(tmp_path: Path) -> None:
    # A rollback run with the home spelled in another case must not leave
    # out the record under the first case: that record is still in place,
    # and only the ledger's own exact match says which one is reversed.
    skill = user_home() / ".agents" / "skills" / "alpha"
    lower, upper = tmp_path / "home" / ".codex", tmp_path / "HOME" / ".codex"
    _record("codex", lower, skill)

    index = holder_index(exclude=("codex", upper))

    assert [h.root for h in index.holders_of(skill)] == [str(lower)]


def _install_codex_under_both_spellings(
    real: Path, linked: Path, monkeypatch: pytest.MonkeyPatch, *, first: str = "real"
) -> None:
    """Install Codex with the home spelled one way, then the other (*first* first)."""
    runner = CliRunner()
    order = (real, linked) if first == "real" else (linked, real)
    for home in order:
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


def _ended(harness: str, *roots: Path) -> bool:
    """Return True when no install of *harness* is in place under any of *roots*."""
    return all(
        install_ledger.current_install_record(harness, root=root) is None
        for root in roots
    )


def _gone(home: Path) -> bool:
    """Return True when the shared folders under *home* hold nothing."""
    return all(
        not (home / folder).exists() or not _files(home / folder) for folder in _SHARED
    )


@pytest.mark.parametrize("first", ["real", "linked"])
@pytest.mark.parametrize("spelling", ["linked", "real"])
def test_one_tool_under_both_spellings_is_one_install_to_an_uninstall(
    homes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, spelling: str, first: str
) -> None:
    # Codex recorded under both spellings of one home: uninstalling it under
    # either spelling, whichever install came first, removes everything
    # either record shows Apothem wrote and ends both records, so nothing is
    # left that a record pins and no uninstall can remove.
    real, linked = homes
    _install_codex_under_both_spellings(real, linked, monkeypatch, first=first)
    home = linked if spelling == "linked" else real

    _spell_home(monkeypatch, home)
    result = CliRunner().invoke(
        main, ["uninstall", "--harness", "codex", "--yes", "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    notes = _shared_notes(result.output)
    assert {Path(str(note["path"])).relative_to(home) for note in notes} == set(_SHARED)
    for note in notes:
        assert note["role"] == "released", note["message"]
        assert note["holders"] == []
    assert _gone(real)
    assert not (real / ".codex").exists(), _files(real / ".codex")
    assert not (real / ".agents").exists()
    assert _ended("codex", real / ".codex", linked / ".codex")
    assert not holder_index().by_path


def test_an_uninstall_removes_what_only_the_other_spelling_lists(
    homes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The two records can differ (two releases, a skill renamed between
    # them). A skill only the record under the real spelling lists goes
    # with an uninstall under the link, which ends that record.
    real, linked = homes
    _install_codex_under_both_spellings(real, linked, monkeypatch)
    extra = real / ".agents" / "skills" / "zz-probe"
    extra.mkdir()
    body = b"# probe\n"
    (extra / "SKILL.md").write_bytes(body)
    current = install_ledger.current_install_record("codex", root=real / ".codex")
    assert current is not None
    probe = LedgerTarget(
        path=str(extra),
        mode="native_skills",
        ownership_class="operator-owned",
        outcome="created",
        created=True,
        files={"SKILL.md": hashlib.sha256(body).hexdigest()},
    )
    install_ledger.append_record(
        LedgerRecord.create(
            harness="codex",
            root=real / ".codex",
            kind="install",
            targets=(*current.targets, probe),
        )
    )

    _spell_home(monkeypatch, linked)
    result = CliRunner().invoke(main, ["uninstall", "--harness", "codex", "--yes"])

    assert result.exit_code == 0, result.output
    assert not extra.exists()
    assert _gone(real)
    assert _ended("codex", real / ".codex", linked / ".codex")


def test_one_tool_under_both_spellings_keeps_the_folders_for_another_tool(
    homes: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real, linked = homes
    _install_codex_under_both_spellings(real, linked, monkeypatch)
    project = tmp_path / "project"
    project.mkdir()
    windsurf = ["--harness", "windsurf", "--project", str(project), "--yes"]
    result = CliRunner().invoke(main, ["install", *windsurf])
    assert result.exit_code == 0, result.output
    before = {folder: _files(real / folder) for folder in _SHARED}

    result = CliRunner().invoke(
        main, ["uninstall", "--harness", "codex", "--yes", "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    notes = _shared_notes(result.output)
    assert notes
    for note in notes:
        assert note["role"] == "retained", note["message"]
        assert note["holders"] == [f"windsurf ({project})"]
    assert {folder: _files(real / folder) for folder in _SHARED} == before
    assert _ended("codex", real / ".codex", linked / ".codex")

    result = CliRunner().invoke(main, ["uninstall", *windsurf])

    assert result.exit_code == 0, result.output
    assert _gone(real)


def _case_insensitive(folder: Path) -> bool:
    return Path(str(folder).swapcase()).exists()


def _install_codex_in_two_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Install Codex with the home spelled ``home``, then ``HOME``; return both."""
    home = tmp_path / "home"
    home.mkdir()
    if not _case_insensitive(home):
        pytest.skip("this file system tells the case of a name apart")
    upper = tmp_path / "HOME"
    for spelled in (home, upper):
        _spell_home(monkeypatch, spelled)
        result = CliRunner().invoke(main, ["install", "--harness", "codex", "--yes"])
        assert result.exit_code == 0, result.output
    return home, upper


def test_a_rollback_under_another_case_keeps_folders_the_first_case_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A rollback under HOME reverses only its own record, so the record
    # under home, still in place, keeps the shared folders it lists.
    home, _upper = _install_codex_in_two_cases(tmp_path, monkeypatch)
    before = {folder: _files(home / folder) for folder in _SHARED}
    assert all(before.values())

    result = CliRunner().invoke(main, ["rollback", "--harness", "codex", "--yes"])

    assert result.exit_code == 0, result.output
    assert {folder: _files(home / folder) for folder in _SHARED} == before
    _spell_home(monkeypatch, home)
    verified = CliRunner().invoke(main, ["verify", "--harness", "codex"])
    assert verified.exit_code == 0, verified.output


def test_an_uninstall_under_another_case_ends_both_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, upper = _install_codex_in_two_cases(tmp_path, monkeypatch)

    result = CliRunner().invoke(main, ["uninstall", "--harness", "codex", "--yes"])

    assert result.exit_code == 0, result.output
    assert _gone(home)
    assert _ended("codex", home / ".codex", upper / ".codex")


def test_the_preview_finds_its_own_install_by_exact_text(tmp_path: Path) -> None:
    skill = user_home() / ".agents" / "skills" / "alpha"
    lower, upper = tmp_path / "home" / ".codex", tmp_path / "HOME" / ".codex"
    _record("codex", lower, skill)
    _record("codex", upper, skill)

    view = LedgerView.load()

    assert view is not None
    found = view.find("codex", upper)
    assert found is not None
    assert found.root == str(upper)
    assert view.find("codex", tmp_path / "Home" / ".codex") is None


def test_rolling_back_the_creator_then_the_last_holder_removes_the_folders(
    tmp_path: Path,
) -> None:
    # Codex creates the shared folders and Windsurf finds them in place.
    # Rolling back Codex keeps them for Windsurf; rolling back Windsurf then
    # removes them, though Codex's install is no longer in place.
    home = user_home()
    project = tmp_path / "project"
    project.mkdir()
    runner = CliRunner()
    windsurf = ["--harness", "windsurf", "--project", str(project), "--yes"]
    for args in (["--harness", "codex", "--yes"], windsurf):
        result = runner.invoke(main, ["install", *args])
        assert result.exit_code == 0, result.output

    first = runner.invoke(main, ["rollback", "--harness", "codex", "--yes"])
    assert first.exit_code == 0, first.output
    assert all(_files(home / folder) for folder in _SHARED)
    last = runner.invoke(main, ["rollback", *windsurf])

    assert last.exit_code == 0, last.output
    assert _gone(home)


def test_rolling_back_both_spellings_creator_first_removes_the_folders(
    homes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    real, linked = homes
    runner = CliRunner()
    for home in (linked, real):
        _spell_home(monkeypatch, home)
        result = runner.invoke(main, ["install", "--harness", "codex", "--yes"])
        assert result.exit_code == 0, result.output
    for home in (linked, real):
        _spell_home(monkeypatch, home)
        result = runner.invoke(main, ["rollback", "--harness", "codex", "--yes"])
        assert result.exit_code == 0, result.output

    assert _gone(real)


def _windsurf(project: Path) -> list[str]:
    project.mkdir(exist_ok=True)
    return ["--harness", "windsurf", "--project", str(project), "--yes"]


def _run(*args: str) -> None:
    result = CliRunner().invoke(main, list(args))
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("both", [False, True], ids=["one-spelling", "both-spellings"])
def test_a_rollback_keeps_folders_put_back_after_an_uninstall_removed_them(
    homes: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    both: bool,
) -> None:
    # Codex makes the shared folders and its uninstall removes them. Folders
    # put back by hand (from a backup, say) are not Apothem's: rolling back
    # Windsurf, which found them in place, keeps them.
    real, linked = homes
    if both:
        _install_codex_under_both_spellings(real, linked, monkeypatch)
        _spell_home(monkeypatch, linked)
    else:
        _spell_home(monkeypatch, real)
        _run("install", "--harness", "codex", "--yes")
    saved = tmp_path / "saved"
    for folder in _SHARED:
        shutil.copytree(real / folder, saved / folder)
    _run("uninstall", "--harness", "codex", "--yes")
    assert _gone(real)
    for folder in _SHARED:
        shutil.copytree(saved / folder, real / folder, dirs_exist_ok=True)
    before = {folder: _files(real / folder) for folder in _SHARED}
    windsurf = _windsurf(tmp_path / "project")
    _run("install", *windsurf)

    _run("rollback", *windsurf)

    assert {folder: _files(real / folder) for folder in _SHARED} == before


@pytest.mark.parametrize("ending", ["rollback", "uninstall"])
def test_the_last_holder_removes_the_folders_after_the_creator_is_reinstalled(
    tmp_path: Path, ending: str
) -> None:
    # Codex makes the folders, Windsurf finds them, Codex is rolled back and
    # installed again (finding them in place). Rolling back or uninstalling
    # every holder still removes them: the first install's record is kept.
    home = user_home()
    windsurf = _windsurf(tmp_path / "project")
    _run("install", "--harness", "codex", "--yes")
    _run("install", *windsurf)
    _run("rollback", "--harness", "codex", "--yes")
    _run("install", "--harness", "codex", "--yes")
    assert all(_files(home / folder) for folder in _SHARED)

    if ending == "rollback":
        _run("rollback", *windsurf)
        _run("rollback", "--harness", "codex", "--yes")
    else:
        _run("uninstall", "--harness", "codex", "--yes")
        _run("rollback", *windsurf)

    assert _gone(home)


def test_the_last_holder_removes_the_folders_after_retention_drops_the_creator(
    tmp_path: Path,
) -> None:
    # Retention keeps the newest installs of a root; an install after it
    # carries the word that the dropped one made the folders.
    home = user_home()
    windsurf = _windsurf(tmp_path / "project")
    _run("install", "--harness", "codex", "--yes")
    _run("install", *windsurf)
    _run("install", "--harness", "codex", "--yes")
    install_ledger.compact_records("codex", keep_installs=1)
    kinds = [record.kind for record in install_ledger.read_records("codex")]
    assert kinds == ["install"]

    _run("uninstall", "--harness", "codex", "--yes")
    assert all(_files(home / folder) for folder in _SHARED)
    _run("rollback", *windsurf)

    assert _gone(home)


def test_one_folder_by_its_file_id_when_links_keep_the_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # On macOS following the links keeps the case as spelled, so two case
    # spellings of one folder differ as text; their file ID is one.
    home = tmp_path / "home"
    home.mkdir()
    if not _case_insensitive(home):
        pytest.skip("this file system tells the case of a name apart")
    (tmp_path / "other").mkdir()
    monkeypatch.setattr(os.path, "realpath", lambda path, **_kw: os.fspath(path))

    assert install_driver_keys.same_folder(home, tmp_path / "HOME")
    assert not install_driver_keys.same_folder(home, tmp_path / "other")
    assert not install_driver_keys.same_folder(home, tmp_path / "missing")


def test_a_case_sensitive_folder_keeps_two_cases_apart(tmp_path: Path) -> None:
    folder = tmp_path / "case-sensitive"
    folder.mkdir()
    if sys.platform != "win32":
        pytest.skip("per-folder case sensitivity is a Windows setting")
    try:
        subprocess.run(
            ["fsutil", "file", "setCaseSensitiveInfo", str(folder), "enable"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("this host cannot make a case-sensitive folder")
    (folder / "Proj").mkdir()
    (folder / "proj").mkdir()

    assert not install_driver_keys.same_folder(folder / "Proj", folder / "proj")


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


# --- compaction keeps who created a shared folder ---------------------------------


def _install_record(root: Path, outcome: str) -> LedgerRecord:
    skill = user_home() / ".agents" / "skills" / "alpha"
    record = LedgerRecord.create(
        harness="codex",
        root=root,
        kind="install",
        targets=(
            LedgerTarget(
                path=str(skill),
                mode="native_skills",
                ownership_class="apothem-owned",
                outcome=outcome,
            ),
        ),
    )
    install_ledger.append_record(record)
    return record


def _end(root: Path, kind: str, install_id: str | None = None) -> None:
    install_ledger.append_record(
        LedgerRecord.create(
            harness="codex", root=root, kind=kind, install_id=install_id
        )
    )


def _kinds_after_compaction(root: Path) -> list[tuple[str, str]]:
    kept = install_ledger.compact_records("codex", keep_installs=1)
    assert install_ledger.current_install_record("codex", root=root) is None
    return [(record.kind, record.install_id) for record in kept]


def test_compaction_keeps_the_rolled_back_creator(tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    first = _install_record(root, "created")
    _end(root, "rollback", first.install_id)

    kept = _kinds_after_compaction(root)

    assert kept == [("install", first.install_id), ("rollback", first.install_id)]


def test_compaction_keeps_only_the_uninstalled_installs_that_created(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".codex"
    first = _install_record(root, "created")
    _install_record(root, "unchanged")
    _end(root, "uninstall")

    kept = _kinds_after_compaction(root)

    assert [kind for kind, _ in kept] == ["install", "uninstall"]
    assert kept[0][1] == first.install_id


def test_compaction_keeps_only_the_last_record_when_nothing_was_created(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".codex"
    _install_record(root, "updated")
    _end(root, "uninstall")

    assert [kind for kind, _ in _kinds_after_compaction(root)] == ["uninstall"]


def test_compaction_does_not_keep_an_install_an_earlier_uninstall_ended(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".codex"
    _install_record(root, "created")
    _end(root, "uninstall")
    second = _install_record(root, "created")
    _end(root, "rollback", second.install_id)

    kept = _kinds_after_compaction(root)

    assert kept == [("install", second.install_id), ("rollback", second.install_id)]


def test_compaction_keeps_only_what_the_ending_record_left(tmp_path: Path) -> None:
    # The uninstall removed alpha (it lists alpha's backup) and kept beta for
    # another install: only beta is still known as made, and no kept record
    # pins a backup set.
    root = tmp_path / ".codex"
    skills = user_home() / ".agents" / "skills"
    made = [
        LedgerTarget(
            path=str(skills / name),
            mode="native_skills",
            ownership_class="apothem-owned",
            outcome="created",
            backup_ref=str(tmp_path / "backup" / name),
        )
        for name in ("alpha", "beta")
    ]
    first = LedgerRecord.create(
        harness="codex", root=root, kind="install", targets=tuple(made)
    )
    install_ledger.append_record(first)
    install_ledger.append_record(
        LedgerRecord.create(
            harness="codex",
            root=root,
            kind="uninstall",
            install_id=first.install_id,
            targets=(made[0],),
        )
    )

    kept = install_ledger.compact_records("codex", keep_installs=1)

    assert [record.kind for record in kept] == ["install", "uninstall"]
    assert [target.path for target in kept[0].targets] == [made[1].path]
    assert kept[0].targets[0].backup_ref is None
    assert kept[1] == install_ledger.read_records("codex")[1]


def test_compaction_keeps_a_rolled_back_creator_before_a_reinstall(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".codex"
    first = _install_record(root, "created")
    _end(root, "rollback", first.install_id)
    second = _install_record(root, "unchanged")

    kept = install_ledger.compact_records("codex", keep_installs=1)

    assert [(r.kind, r.install_id) for r in kept] == [
        ("install", first.install_id),
        ("rollback", first.install_id),
        ("install", second.install_id),
    ]
    current = install_ledger.current_install_record("codex", root=root)
    assert current is not None
    assert current.install_id == second.install_id


def test_compaction_keeps_a_creator_a_rollback_of_an_earlier_install_ended(
    tmp_path: Path,
) -> None:
    # A rollback of the first install ends the second one too; the second
    # made alpha, so it is kept, with the first, which the rollback names.
    root = tmp_path / ".codex"
    first = _install_record(root, "unchanged")
    second = _install_record(root, "created")
    _end(root, "rollback", first.install_id)

    kept = _kinds_after_compaction(root)

    assert kept == [
        ("install", first.install_id),
        ("install", second.install_id),
        ("rollback", first.install_id),
    ]
