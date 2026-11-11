# SPDX-License-Identifier: MIT

"""The Python API and the CLI read and write one install record per project.

The CLI resolves ``--project`` before it reads or writes an install record;
a Python caller passes the project folder as it typed it, a link included.
Every project-scope entry point spells the folder the way the install
records already do (:func:`apothem.lib.install_ledger.recorded_root`), so an
install made one way is found, updated and removed the other way, and a new
install records the folder resolved, as the CLI does.

Creating a symbolic link needs a privilege some Windows hosts lack, so there
each link is a junction.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner, Result

from apothem.cli import main
from apothem.harnesses._shared import install_driver_materialize, wrapper_factories
from apothem.harnesses._shared.install_driver_datahome import shell_quoted
from apothem.harnesses._shared.install_driver_types import MaterializationError, _result
from apothem.harnesses.cursor import CursorAdapter
from apothem.harnesses.cursor.install import install as cursor_install
from apothem.harnesses.kimi_code.install import install as kimi_install
from apothem.harnesses.kimi_code.uninstall import uninstall as kimi_uninstall
from apothem.lib import install_ledger
from tests._shared.case_sensitive import case_sensitive_folder


def _link(link: Path, target: Path) -> None:
    """Make *link* lead to *target*: a symbolic link, or a junction on Windows."""
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot create a directory link")
        import _winapi

        _winapi.CreateJunction(str(target), str(link))


@pytest.fixture
def linked(tmp_path: Path) -> tuple[Path, Path]:
    """Return ``(project as typed, the folder it leads to)``."""
    outside = tmp_path / "outside" / "proj"
    _link(tmp_path / "proj", outside)
    return tmp_path / "proj", outside.resolve()


@pytest.fixture
def profile(tmp_path: Path) -> dict[str, Any]:
    path = tmp_path / "prof" / "profile.yaml"
    made = CliRunner().invoke(main, ["profile", "init", "--profile", str(path)])
    assert made.exit_code == 0, made.output
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _as_typed(patch: pytest.MonkeyPatch) -> None:
    """Make the install record the folder as typed, as an earlier release did."""
    patch.setattr(wrapper_factories, "recorded_root", lambda _h, root: root)
    patch.setattr(wrapper_factories, "install_spelling", lambda _h, root: (root, None))


def _install_as_typed(
    monkeypatch: pytest.MonkeyPatch, project: Path, profile: dict[str, Any]
) -> None:
    """Install through the API the way an earlier release did: as typed."""
    with monkeypatch.context() as patch:
        _as_typed(patch)
        run = cursor_install(project / ".cursor", profile, project=project)
    assert not run.errors, [error.message for error in run.errors]
    assert install_ledger.latest_record("cursor").root == str(project)


def _files(folder: Path) -> list[Path]:
    return sorted(path for path in folder.rglob("*") if path.is_file())


def _cli(*args: str) -> Result:
    return CliRunner().invoke(main, list(args))


def test_a_new_api_install_through_a_link_records_the_folder_resolved(
    linked: tuple[Path, Path], profile: dict[str, Any]
) -> None:
    project, outside = linked

    run = cursor_install(project / ".cursor", profile, project=project)

    assert not run.errors, [error.message for error in run.errors]
    assert install_ledger.latest_record("cursor").root == str(outside)
    assert _files(outside)


@pytest.mark.parametrize("earlier_release", [False, True])
def test_the_cli_uninstalls_an_api_install_made_through_a_link(
    linked: tuple[Path, Path],
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    earlier_release: bool,
) -> None:
    project, outside = linked
    if earlier_release:
        _install_as_typed(monkeypatch, project, profile)
    else:
        run = cursor_install(project / ".cursor", profile, project=project)
        assert not run.errors
    assert _files(outside)

    status = _cli("status", "--project", str(project))
    result = _cli(
        "uninstall", "--harness", "cursor", "--project", str(project), "--yes"
    )

    assert any(
        "cursor" in line and "installed=True" in line
        for line in status.output.splitlines()
    ), status.output
    assert result.exit_code == 0, result.output
    assert "were kept" not in result.output, result.output
    assert _files(outside) == []
    latest = install_ledger.latest_record("cursor", kind=None)
    assert latest is not None
    assert latest.kind == "uninstall"
    assert latest.root == (str(project) if earlier_release else str(outside))
    # The notes on the shared folders read the same record.
    assert "no other Apothem install uses it" in " ".join(result.output.split())


def test_the_api_finds_an_install_recorded_as_typed(
    linked: tuple[Path, Path],
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, outside = linked
    _install_as_typed(monkeypatch, project, profile)
    adapter = CursorAdapter()

    found = adapter.is_installed(project=outside)
    verified = adapter.verify(project=outside)
    run = adapter.uninstall(project=outside)

    assert found
    assert verified
    assert not run.errors, [error.message for error in run.errors]
    assert _files(outside) == []
    latest = install_ledger.latest_record("cursor", kind=None)
    assert latest is not None
    assert (latest.kind, latest.root) == ("uninstall", str(project))


def test_rollback_finds_an_api_install_recorded_as_typed(
    linked: tuple[Path, Path],
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, outside = linked
    _install_as_typed(monkeypatch, project, profile)

    result = _cli("rollback", "--harness", "cursor", "--project", str(project), "--yes")

    assert result.exit_code == 0, result.output
    # The data folders the install made (memory, learning, contexts) hold the
    # operator's data, which a rollback keeps.
    assert _files(outside / ".cursor") == []
    assert _files(outside / ".apothem" / "support") == []
    latest = install_ledger.latest_record("cursor", kind=None)
    assert latest is not None
    assert (latest.kind, latest.root) == ("rollback", str(project))


def _record(root: Path) -> install_ledger.LedgerRecord:
    return install_ledger.LedgerRecord.create(
        harness="cursor", root=root, kind="install", targets=()
    )


def test_the_spelling_rule_prefers_the_spelling_a_record_uses(
    linked: tuple[Path, Path],
) -> None:
    project, outside = linked
    other = outside.parent / "other"
    other.mkdir()

    assert install_ledger.recorded_root("cursor", project) == outside
    install_ledger.append_record(_record(outside))
    assert install_ledger.recorded_root("cursor", project) == outside
    install_ledger.append_record(_record(project))
    assert install_ledger.recorded_root("cursor", project) == project
    assert install_ledger.recorded_root("cursor", outside) == outside
    assert install_ledger.recorded_root("cursor", other) == other.resolve()


def test_a_corrupt_ledger_gives_the_folder_resolved(
    linked: tuple[Path, Path],
) -> None:
    project, outside = linked
    ledger = install_ledger.ledger_path("cursor")
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(b"not json\n{}\n")

    assert install_ledger.recorded_root("cursor", project) == outside


def test_kimi_code_uninstall_finds_an_install_recorded_as_typed(
    linked: tuple[Path, Path],
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Kimi Code has its own uninstall in front of the shared one.
    project, outside = linked
    with monkeypatch.context() as patch:
        _as_typed(patch)
        run = kimi_install(project / "AGENTS.md", profile, project=project)
    assert not run.errors, [error.message for error in run.errors]
    assert install_ledger.latest_record("kimi_code").root == str(project)

    run = kimi_uninstall(outside / "AGENTS.md", project=outside)

    assert not run.errors, [error.message for error in run.errors]
    assert _files(outside / ".kimi-code") == []
    latest = install_ledger.latest_record("kimi_code", kind=None)
    assert latest is not None
    assert (latest.kind, latest.root) == ("uninstall", str(project))


@pytest.mark.parametrize("typed", ["proj", "~/proj"])
def test_a_relative_record_does_not_capture_the_cli_folder(
    tmp_path: Path,
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    typed: str,
) -> None:
    # An earlier Python call recorded the folder as typed, relative to the
    # folder it ran from (the driver never expanded ``~``). That names a
    # folder somewhere else, even when the same words, read from here, name
    # the folder the CLI is given; the CLI writes and records that folder.
    install_ledger.append_record(_record(Path(typed)))
    monkeypatch.chdir(tmp_path)
    project = Path(typed).expanduser().absolute()
    project.mkdir()

    assert install_ledger.recorded_root("cursor", project) == project.resolve()
    installed = _cli(
        "install",
        "--harness",
        "cursor",
        "--project",
        str(project),
        "--profile",
        str(tmp_path / "prof" / "profile.yaml"),
        "--yes",
    )
    assert installed.exit_code == 0, installed.output
    assert install_ledger.latest_record("cursor").root == str(project.resolve())
    assert _files(project / ".cursor")
    removed = _cli(
        "uninstall", "--harness", "cursor", "--project", str(project), "--yes"
    )

    assert removed.exit_code == 0, removed.output
    assert _files(project / ".cursor") == []
    records = install_ledger.read_records("cursor")
    assert [(r.kind, r.root) for r in records if r.root == str(Path(typed))] == [
        ("install", str(Path(typed)))
    ]
    assert records[-1].kind == "uninstall"
    assert records[-1].root == str(project.resolve())


def _install_cli(project: Path, tmp_path: Path, profile: Path | None = None) -> None:
    result = _cli(
        "install",
        "--harness",
        "cursor",
        "--project",
        str(project),
        "--profile",
        str(profile or tmp_path / "prof" / "profile.yaml"),
        "--yes",
    )
    assert result.exit_code == 0, result.output


@pytest.fixture
def case_pair(tmp_path: Path, profile: dict[str, Any]) -> tuple[Path, Path]:
    """Return ``(Proj, proj)``: two folders whose names differ only in case.

    ``Proj`` holds a command-line install; ``proj`` holds a file of the
    user's own.
    """
    folder = tmp_path / "cs"
    case_sensitive_folder(folder)
    upper, lower = folder / "Proj", folder / "proj"
    upper.mkdir()
    lower.mkdir()
    (lower / "notes.md").write_text("mine", encoding="utf-8")
    _install_cli(upper, tmp_path)
    return upper, lower


def test_a_case_only_sibling_is_another_folder_on_uninstall(
    case_pair: tuple[Path, Path],
) -> None:
    # Path equality on Windows ignores case; Proj and proj here are two
    # folders, so uninstalling proj must not remove Proj's install.
    upper, lower = case_pair
    installed = _files(upper)

    assert str(install_ledger.recorded_root("cursor", lower)) == str(lower.resolve())
    result = _cli("uninstall", "--harness", "cursor", "--project", str(lower), "--yes")

    assert result.exit_code == 0, result.output
    assert "Uninstalled" not in result.output, result.output
    # No note about the shared folders: they are Proj's, not proj's.
    assert "Note:" not in result.output, result.output
    assert _files(upper) == installed
    assert _files(lower) == [lower / "notes.md"]
    latest = install_ledger.latest_record("cursor", kind=None)
    assert latest is not None
    assert (latest.kind, latest.root) == ("install", str(upper.resolve()))


def test_a_case_only_sibling_is_another_folder_on_install(
    tmp_path: Path, case_pair: tuple[Path, Path]
) -> None:
    upper, lower = case_pair
    edited = upper / ".cursor" / "agents" / "fact-checker.md"
    edited.write_text("edited in Proj", encoding="utf-8")

    _install_cli(lower, tmp_path)

    assert edited.read_text(encoding="utf-8") == "edited in Proj"
    assert (lower / ".cursor" / "agents" / "fact-checker.md").is_file()
    roots = [record.root for record in install_ledger.read_records("cursor")]
    assert roots == [str(upper.resolve()), str(lower.resolve())]


def test_a_live_install_wins_over_an_uninstalled_spelling(
    tmp_path: Path,
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The folder was installed and uninstalled from the command line, then
    # an earlier release installed it again through a link, as typed. The
    # live install is the one an uninstall must find, under either spelling.
    folder = (tmp_path / "outside" / "X").resolve()
    folder.mkdir(parents=True)
    _install_cli(folder, tmp_path)
    removed = _cli(
        "uninstall", "--harness", "cursor", "--project", str(folder), "--yes"
    )
    assert removed.exit_code == 0, removed.output
    link = tmp_path / "l1"
    _link(link, folder)
    _install_as_typed(monkeypatch, link, profile)

    assert install_ledger.recorded_root("cursor", folder) == link
    assert install_ledger.recorded_root("cursor", link) == link
    result = _cli("uninstall", "--harness", "cursor", "--project", str(link), "--yes")

    assert result.exit_code == 0, result.output
    assert "were kept" not in result.output, result.output
    assert _files(folder) == []
    latest = install_ledger.latest_record("cursor", kind=None)
    assert latest is not None
    assert (latest.kind, latest.root) == ("uninstall", str(link))


def _record_with_file(root: Path, name: str) -> install_ledger.LedgerRecord:
    target = install_ledger.LedgerTarget(
        path=str(root / ".cursor" / name),
        mode="write",
        ownership_class="apothem-owned",
        digest="0" * 64,
    )
    return install_ledger.LedgerRecord.create(
        harness="cursor", root=root, kind="install", targets=(target,)
    )


def test_the_install_whose_files_are_in_the_folder_wins(tmp_path: Path) -> None:
    # Two installs reached one folder through their own links (l1 used to
    # lead elsewhere). The one whose recorded files are in the folder is
    # taken, though the other is newer; when both have their files there,
    # the newest wins. Two real installs of one release write the same
    # names and cannot be told apart this way, so these records, with one
    # file each, stand in for installs from two releases.
    folder = tmp_path / "Y"
    (folder / ".cursor").mkdir(parents=True)
    (folder / ".cursor" / "b.md").write_text("b", encoding="utf-8")
    first, second = tmp_path / "l2", tmp_path / "l1"
    _link(first, folder)
    _link(second, folder)
    install_ledger.append_record(_record_with_file(first, "b.md"))
    install_ledger.append_record(_record_with_file(second, "a.md"))

    assert install_ledger.recorded_root("cursor", folder.resolve()) == first
    (folder / ".cursor" / "a.md").write_text("a", encoding="utf-8")
    assert install_ledger.recorded_root("cursor", folder.resolve()) == second


def test_an_install_with_none_of_its_files_in_the_folder_is_not_taken(
    tmp_path: Path,
) -> None:
    # l1 was pointed at Y after an install through it wrote its files to X.
    folder = tmp_path / "Y"
    folder.mkdir()
    link = tmp_path / "l1"
    _link(link, folder)
    install_ledger.append_record(_record_with_file(link, "a.md"))

    assert install_ledger.recorded_root("cursor", folder) == folder.resolve()
    (folder / ".cursor").mkdir()
    (folder / ".cursor" / "a.md").write_text("a", encoding="utf-8")
    assert install_ledger.recorded_root("cursor", folder) == link


def test_a_file_id_of_zero_does_not_join_two_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Some network and cloud drives report the same file ID, 0, for every
    # folder, so file identity alone would take B for A.
    first, second = tmp_path / "A", tmp_path / "B"
    for folder in (first, second):
        (folder / ".cursor").mkdir(parents=True)
        (folder / ".cursor" / "a.md").write_text("a", encoding="utf-8")
    install_ledger.append_record(_record_with_file(first, "a.md"))
    real_stat = Path.stat
    folders = {str(first), str(second), str(first.resolve()), str(second.resolve())}

    # Path.stat is patched, not os.stat: on Python 3.10, Path.stat calls the
    # os.stat it bound when pathlib was imported, so patching os.stat there
    # would not reach the code under test.
    def stat(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        found = real_stat(self, follow_symlinks=follow_symlinks)
        if str(self) not in folders:
            return found
        fields = list(found[:10])
        fields[1] = 0  # st_ino
        return os.stat_result(fields)

    monkeypatch.setattr(Path, "stat", stat)

    assert os.path.samestat(first.stat(), second.stat())
    assert install_ledger.recorded_root("cursor", second) == second.resolve()


@pytest.mark.skipif(
    sys.platform != "win32", reason="network share paths are Windows paths"
)
def test_a_record_on_another_network_share_is_not_looked_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A share that cannot be reached stalls each lookup for many seconds.
    share = Path("\\\\10.255.255.1\\share\\proj")
    install_ledger.append_record(_record_with_file(share, "a.md"))
    folder = tmp_path / "Y"
    folder.mkdir()
    real_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        assert not str(self).startswith("\\\\10."), f"looked up {self}"
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    assert install_ledger.recorded_root("cursor", folder) == folder.resolve()


def test_the_retention_note_names_the_case_only_sibling(
    tmp_path: Path, case_pair: tuple[Path, Path]
) -> None:
    # Proj and proj both hold an install; uninstalling proj keeps the shared
    # folders for Proj, and the note names Proj, not proj.
    upper, lower = case_pair
    _install_cli(lower, tmp_path)

    result = _cli(
        "uninstall",
        "--harness",
        "cursor",
        "--project",
        str(lower),
        "--yes",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    notes = [
        str(warning["message"])
        for warning in json.loads(result.output)["warnings"]
        if "still used by" in str(warning.get("message", ""))
    ]
    assert notes
    for note in notes:
        assert f"{os.sep}{upper.name})" in note, note
        assert f"{os.sep}{lower.name})" not in note, note
    # The folders are kept, not only said to be: Proj still uses them.
    assert CursorAdapter().verify(project=upper.resolve())
    assert install_ledger.current_install_record("cursor", root=str(upper.resolve()))


def _uninstall_without_record(folder: Path, tmp_path: Path, fmt: str) -> Result:
    """Install into *folder*, delete the ledger, then uninstall in *fmt*."""
    _install_cli(folder, tmp_path)
    install_ledger.ledger_path("cursor").unlink()
    args = ["uninstall", "--harness", "cursor", "--project", str(folder), "--yes"]
    return _cli(*args, *(["--format", "json"] if fmt == "json" else []))


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_an_uninstall_that_matches_no_record_does_not_say_uninstalled(
    tmp_path: Path, profile: dict[str, Any], fmt: str
) -> None:
    folder = tmp_path / "X"
    folder.mkdir()
    result = _uninstall_without_record(folder, tmp_path, fmt)

    # No record shows which files Apothem wrote, so the uninstall does not
    # finish; it removed some files first, so it exits 2.
    assert result.exit_code == 2, result.output
    assert _files(folder / ".cursor" / "agents")
    assert not (folder / ".cursor" / "rules" / "apothem-rules.mdc").exists()
    if fmt == "json":
        rows = json.loads(result.output)["results"]
        assert [row["operation"] for row in rows] == ["uninstall"]
        assert rows[0]["outcome"] == "error"
        assert rows[0]["detail"] == {"kept_reason": "no-record"}
        message = rows[0]["message"]
        assert "first copy any listed file you edited or added" in message
        assert "then run apothem update, then apothem uninstall again" in message
        assert "; no install record matched" in message
        assert (
            "2 Apothem-only files and the memory, contexts and learning stores "
            "in its data folder (backed up) were removed"
        ) in message
        quoted = shell_quoted(str(folder))
        assert (
            f"before you run apothem update, check that --project {quoted} is "
            "the folder you installed into"
        ) in message
        assert "apothem install" not in message
    else:
        text = " ".join(result.output.split())
        assert "Uninstalled cursor" not in text
        assert "cursor uninstall did not finish" in text
        # The grouped warning line lists the kept paths; the Note line adds
        # what was left in the home folder and what was still removed.
        assert "paths were kept: no install record shows whether Apothem" in text
        assert "Note: cursor - no install record matched" in text


def test_a_quiet_uninstall_that_matches_no_record_still_says_so(
    tmp_path: Path, profile: dict[str, Any]
) -> None:
    folder = tmp_path / "X"
    folder.mkdir()
    _install_cli(folder, tmp_path)
    install_ledger.ledger_path("cursor").unlink()

    result = _cli(
        "uninstall", "--harness", "cursor", "--project", str(folder), "--yes", "-q"
    )

    assert result.exit_code == 2, result.output
    words = " ".join(result.output.split())
    assert "cursor uninstall did not finish" in words
    assert "Note: cursor - no install record matched" in words


def test_a_failing_uninstall_that_matches_no_record_still_says_so(
    tmp_path: Path, profile: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "X"
    folder.mkdir()
    _install_cli(folder, tmp_path)
    install_ledger.ledger_path("cursor").unlink()
    real_unlink = Path.unlink

    def unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name == "apothem-rules.mdc":
            raise PermissionError(13, "The file is in use")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    args = ["uninstall", "--harness", "cursor", "--project", str(folder), "--yes"]
    text = _cli(*args)
    data = _cli(*args, "--format", "json")
    quiet = _cli(*args, "-q")

    assert text.exit_code == 2, text.output
    words = " ".join(text.output.split())
    assert "Note: cursor - no install record matched" in words
    assert "paths were kept: no install record shows whether Apothem" in words
    # The earlier runs removed the rest, so this one removed nothing; the
    # paths kept for want of a record still make it partial: exit 2.
    assert quiet.exit_code == 2, quiet.output
    assert "Note: cursor - no install record matched" in " ".join(quiet.output.split())
    rows = json.loads(data.output)["results"]
    assert rows[0]["outcome"] == "error", rows
    assert rows[0]["detail"]["kept_reason"] == "no-record"
    assert "no install record matched" in rows[0]["message"]


def test_an_uninstall_that_matches_no_record_and_removes_nothing(
    tmp_path: Path, profile: dict[str, Any]
) -> None:
    folder = tmp_path / "X"
    folder.mkdir()
    _install_cli(folder, tmp_path)
    install_ledger.ledger_path("cursor").unlink()
    (folder / ".cursor" / "rules" / "apothem-rules.mdc").unlink()
    (folder / ".cursor" / "hooks.json").unlink()
    for store in ("contexts", "learning", "memory"):
        shutil.rmtree(folder / ".apothem" / store)
    installed = _files(folder)

    result = _cli(
        "uninstall",
        "--harness",
        "cursor",
        "--project",
        str(folder),
        "--yes",
        "--format",
        "json",
    )

    assert result.exit_code == 2, result.output
    rows = json.loads(result.output)["results"]
    assert rows[0]["outcome"] == "error", rows
    assert rows[0]["detail"] == {"kept_reason": "no-record"}
    assert " were removed" not in rows[0]["message"], rows[0]["message"]
    assert " was removed" not in rows[0]["message"], rows[0]["message"]
    assert _files(folder) == installed
    text = _cli("uninstall", "--harness", "cursor", "--project", str(folder), "--yes")
    words = " ".join(text.output.split())
    assert "Uninstalled cursor" not in words
    assert "Note: cursor - no install record matched" in words


def _unlink_folder_link(link: Path) -> None:
    """Remove the link *link* itself: a junction or a symbolic link."""
    try:
        link.rmdir()
    except OSError:
        link.unlink()


def test_an_install_moves_a_record_kept_under_a_link_to_the_folder(
    tmp_path: Path,
    linked: tuple[Path, Path],
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An earlier release recorded the install under the link. A command-line
    # install records the folder resolved and moves that install there, so it
    # is still found, and removed, once the link is gone.
    project, outside = linked
    _install_as_typed(monkeypatch, project, profile)

    _install_cli(outside, tmp_path)

    assert install_ledger.active_install_records("cursor", root=project) == []
    active = install_ledger.active_install_records("cursor", root=outside)
    assert len(active) == 2
    below_link = str(project) + os.sep
    assert not any(t.path.startswith(below_link) for r in active for t in r.targets)
    _unlink_folder_link(project)
    result = _cli(
        "uninstall", "--harness", "cursor", "--project", str(outside), "--yes"
    )

    assert result.exit_code == 0, result.output
    assert "Uninstalled" in result.output, result.output
    assert "were kept" not in result.output, result.output
    assert _files(outside) == []
    for root in {record.root for record in install_ledger.read_records("cursor")}:
        assert install_ledger.active_install_records("cursor", root=root) == []


def test_moving_an_install_moves_its_paths_and_unfinished_uninstall(
    tmp_path: Path, linked: tuple[Path, Path]
) -> None:
    project, outside = linked
    (outside / ".cursor").mkdir()
    (outside / ".cursor" / "a.md").write_text("a", encoding="utf-8")
    inside = install_ledger.LedgerTarget(
        path=str(project / ".cursor" / "a.md"),
        mode="write",
        ownership_class="apothem-owned",
        digest="0" * 64,
    )
    shared = install_ledger.LedgerTarget(
        path=str(tmp_path / "home" / ".agents" / "skills" / "x"),
        mode="write",
        ownership_class="apothem-owned",
    )
    record = install_ledger.LedgerRecord.create(
        harness="cursor",
        root=project,
        kind="install",
        targets=(inside, shared),
        created_dirs=(str(project / ".cursor"),),
        data_home=str(project / ".apothem"),
    )
    install_ledger.append_record(record)
    install_ledger.append_record(
        install_ledger.LedgerRecord.create(
            harness="cursor",
            root=project,
            kind="uninstall-incomplete",
            install_id=record.install_id,
        )
    )

    assert install_ledger.install_spelling("cursor", project) == (outside, project)
    install_ledger.move_install("cursor", project, outside)

    (moved,) = install_ledger.active_install_records("cursor", root=outside)
    assert moved.install_id == record.install_id
    assert [t.path for t in moved.targets] == [
        str(outside / ".cursor" / "a.md"),
        shared.path,
    ]
    assert moved.created_dirs == (str(outside / ".cursor"),)
    assert moved.data_home == str(outside / ".apothem")
    assert install_ledger.unfinished_uninstall("cursor", root=outside) is not None
    assert install_ledger.active_install_records("cursor", root=project) == []
    count = len(install_ledger.read_records("cursor"))
    assert install_ledger.install_spelling("cursor", project) == (outside, None)
    install_ledger.move_install("cursor", project, outside)
    assert len(install_ledger.read_records("cursor")) == count


def test_an_install_keeps_a_live_relative_record_as_given(tmp_path: Path) -> None:
    # A relative record names a folder relative to where an earlier Python
    # call ran, so it cannot be moved; that caller keeps writing under it.
    install_ledger.append_record(_record(Path("proj")))

    assert install_ledger.install_spelling("cursor", Path("proj")) == (
        Path("proj"),
        None,
    )
    assert len(install_ledger.read_records("cursor")) == 1


def test_a_python_reinstall_through_a_link_records_the_folder_resolved(
    linked: tuple[Path, Path],
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The link's install was removed; its record still uses the link, but a
    # new install records the folder resolved.
    project, outside = linked
    _install_as_typed(monkeypatch, project, profile)
    removed = CursorAdapter().uninstall(project=project)
    assert not removed.errors, [error.message for error in removed.errors]

    run = cursor_install(project / ".cursor", profile, project=project)

    assert not run.errors, [error.message for error in run.errors]
    assert install_ledger.latest_record("cursor").root == str(outside)


def test_an_unfinished_uninstall_under_a_link_is_still_found(tmp_path: Path) -> None:
    # The unfinished uninstall removed every file of the folder; its install
    # is still taken, so running the uninstall again finishes it.
    folder = tmp_path / "Y"
    folder.mkdir()
    link = tmp_path / "l1"
    _link(link, folder)
    record = _record_with_file(link, "a.md")
    install_ledger.append_record(record)

    assert install_ledger.recorded_root("cursor", folder) == folder.resolve()
    install_ledger.append_record(
        install_ledger.LedgerRecord.create(
            harness="cursor",
            root=link,
            kind="uninstall-incomplete",
            install_id=record.install_id,
        )
    )
    assert install_ledger.recorded_root("cursor", folder) == link


def test_an_unfinished_uninstall_through_a_link_finishes_on_the_next_run(
    tmp_path: Path,
    linked: tuple[Path, Path],
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Another program holds the rules file, so the first run cannot delete
    # it: it does not finish and says so. The second run finishes.
    project, outside = linked
    _install_as_typed(monkeypatch, project, profile)
    rules = outside / ".cursor" / "rules" / "apothem-rules.mdc"
    real_unlink = Path.unlink

    def unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name == rules.name:
            raise PermissionError(13, "The file is in use")
        real_unlink(self, missing_ok=missing_ok)

    args = ("uninstall", "--harness", "cursor", "--project", str(outside), "--yes")
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", unlink)
        first = _cli(*args)
    assert first.exit_code == 2, first.output
    assert "an Apothem-only file" in first.output
    assert rules.exists()

    second = _cli(*args)

    assert second.exit_code == 0, second.output
    assert "Uninstalled" in second.output, second.output
    assert _files(outside) == []


def test_the_install_with_more_files_in_the_folder_wins(tmp_path: Path) -> None:
    # l1 lists more files and lacks one; l2, newer, lists one file only.
    folder = tmp_path / "Y"
    (folder / ".cursor").mkdir(parents=True)
    for name in ("a.md", "b.md"):
        (folder / ".cursor" / name).write_text(name, encoding="utf-8")
    first, second = tmp_path / "l1", tmp_path / "l2"
    _link(first, folder)
    _link(second, folder)
    targets = tuple(
        install_ledger.LedgerTarget(
            path=str(first / ".cursor" / name),
            mode="write",
            ownership_class="apothem-owned",
            digest="0" * 64,
        )
        for name in ("a.md", "b.md", "c.md")
    )
    install_ledger.append_record(
        install_ledger.LedgerRecord.create(
            harness="cursor", root=first, kind="install", targets=targets
        )
    )
    install_ledger.append_record(_record_with_file(second, "a.md"))

    assert install_ledger.recorded_root("cursor", folder.resolve()) == first


def test_a_cloned_volume_is_not_the_same_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A clone of a volume, attached beside it, keeps its serial number and
    # file IDs; only the volume names tell the two apart.
    first, second = tmp_path / "A", tmp_path / "B"
    for folder in (first, second):
        (folder / ".cursor").mkdir(parents=True)
        (folder / ".cursor" / "a.md").write_text("a", encoding="utf-8")
    install_ledger.append_record(_record_with_file(first, "a.md"))
    real_stat = Path.stat
    same = real_stat(first)
    # Spelled before the patch: on Python 3.12 and earlier, Path.resolve and
    # Path.exists call Path.stat, so resolving inside it never returns.
    clone = {str(second), str(second.resolve())}

    def stat(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if str(self) in clone:
            return same
        return real_stat(self, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", stat)
    monkeypatch.setattr(
        install_ledger,
        "_volume_name",
        lambda path: "B" if "B" in Path(path).name else "A",
    )

    assert install_ledger.recorded_root("cursor", second) == second.resolve()
    monkeypatch.setattr(install_ledger, "_volume_name", lambda path: None)
    assert install_ledger.recorded_root("cursor", second) == first


@pytest.mark.skipif(sys.platform != "win32", reason="volume names are Windows names")
def test_the_volume_name_is_read_on_windows(tmp_path: Path) -> None:
    name = install_ledger._volume_name(tmp_path)

    assert name is not None
    assert name.startswith("\\\\?\\Volume{")
    assert install_ledger._volume_name(tmp_path.parent) == name


@pytest.mark.skipif(
    sys.platform != "win32", reason="network share paths are Windows paths"
)
def test_a_share_spelled_in_another_case_is_the_same_share(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Windows gives a share's server and share names in the case of the
    # connection that is open, which can change between sessions.
    recorded = Path("\\\\Server\\Share\\proj")
    install_ledger.append_record(_record(recorded))
    folder = Path("\\\\server\\share\\proj")

    def resolve(self: Path, strict: bool = False) -> Path:
        return Path(str(self).replace("Server\\Share", "server\\share"))

    monkeypatch.setattr(Path, "resolve", resolve)

    # Text, not Path equality, which ignores case on Windows.
    assert str(install_ledger.recorded_root("cursor", folder)) == str(recorded)


@pytest.mark.skipif(sys.platform != "win32", reason="drive letters are Windows paths")
def test_a_record_on_a_mapped_drive_is_not_looked_up_from_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Z: is mapped to a share that cannot be reached now.
    install_ledger.append_record(_record_with_file(Path("Z:\\proj"), "a.md"))
    monkeypatch.setattr(
        install_ledger, "_drive_type", lambda drive: 4 if drive == "Z:" else 3
    )
    monkeypatch.setattr(install_ledger, "_mapped_share", lambda drive: None)
    folder = tmp_path / "Y"
    folder.mkdir()
    resolved = folder.resolve()
    real_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        assert not str(self).startswith("Z:"), f"looked up {self}"
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    assert install_ledger.recorded_root("cursor", resolved) == resolved


@pytest.mark.skipif(sys.platform != "win32", reason="drive letters are Windows paths")
def test_a_record_on_a_mapped_drive_is_found_from_its_share(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Z: is connected to \\srv\share, which the command line spells resolved.
    recorded = Path("Z:\\proj")
    install_ledger.append_record(_record(recorded))
    monkeypatch.setattr(
        install_ledger, "_drive_type", lambda drive: 4 if drive == "Z:" else 3
    )
    monkeypatch.setattr(install_ledger, "_mapped_share", lambda drive: "\\\\srv\\share")
    folder = Path("\\\\SRV\\share\\proj")

    def resolve(self: Path, strict: bool = False) -> Path:
        return Path(str(self).replace("Z:", "\\\\SRV\\share"))

    monkeypatch.setattr(Path, "resolve", resolve)

    assert str(install_ledger.recorded_root("cursor", folder)) == str(recorded)


@pytest.mark.skipif(sys.platform != "win32", reason="long paths are Windows paths")
def test_an_extended_length_record_is_not_taken_for_a_share(tmp_path: Path) -> None:
    folder = (tmp_path / "Y").resolve()
    (folder / ".cursor").mkdir(parents=True)
    (folder / ".cursor" / "a.md").write_text("a", encoding="utf-8")
    recorded = Path("\\\\?\\" + str(folder))
    install_ledger.append_record(_record_with_file(recorded, "a.md"))

    assert install_ledger.recorded_root("cursor", folder) == recorded


def test_a_refused_install_leaves_the_record_where_it_was(
    linked: tuple[Path, Path],
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The install moves a record kept under a link only once its plan passed
    # validation, so an install that is refused changes nothing.
    project, outside = linked
    _install_as_typed(monkeypatch, project, profile)
    before = install_ledger.read_records("cursor")
    refusal = _result("error", "install", outside, "refused for the test")
    with monkeypatch.context() as patch:
        patch.setattr(
            install_driver_materialize,
            "_validate_install_plan",
            lambda *_args, **_kwargs: [refusal],
        )
        with pytest.raises(MaterializationError):
            cursor_install(project / ".cursor", profile, project=project)

    assert install_ledger.read_records("cursor") == before
    run = cursor_install(project / ".cursor", profile, project=project)
    assert not run.errors, [error.message for error in run.errors]
    assert install_ledger.active_install_records("cursor", root=project) == []
    assert len(install_ledger.active_install_records("cursor", root=outside)) == 2


def test_an_install_through_a_disk_only_alias_keeps_the_recorded_spelling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A share path such as \\localhost\C$\X is one folder on disk with the
    # C:\X a record has, but a lookup of C:\X never finds a record kept under
    # the share. So the install keeps the record's own spelling and moves
    # nothing.
    folder, alias = (tmp_path / "X").resolve(), (tmp_path / "alias").resolve()
    for each in (folder, alias):
        (each / ".cursor").mkdir(parents=True)
        (each / ".cursor" / "a.md").write_text("a", encoding="utf-8")
    install_ledger.append_record(_record_with_file(folder, "a.md"))
    one = {str(folder), str(alias)}
    monkeypatch.setattr(
        install_ledger,
        "_same_on_disk",
        lambda left, right: {str(left), str(right)} == one,
    )

    assert install_ledger.recorded_root("cursor", alias) == folder
    assert install_ledger.install_spelling("cursor", alias) == (folder, None)


def test_an_install_through_a_link_to_an_installed_folder_moves_nothing(
    tmp_path: Path,
) -> None:
    # l1 was pointed at Y, which holds an install of its own: moving l1's
    # install there would merge two folders' installs, so it stays.
    folder = (tmp_path / "Y").resolve()
    folder.mkdir()
    link = tmp_path / "l1"
    _link(link, folder)
    install_ledger.append_record(_record_with_file(folder, "b.md"))
    install_ledger.append_record(_record_with_file(link, "a.md"))

    assert install_ledger.recorded_root("cursor", link) == link
    assert install_ledger.install_spelling("cursor", link) == (folder, None)


def test_a_second_record_of_the_folder_does_not_keep_its_data_stores(
    tmp_path: Path,
    linked: tuple[Path, Path],
    profile: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An earlier release recorded the folder twice: from the command line,
    # and from Python through a link. The link's record is the same install
    # in the same folder, so it does not keep the folder's data stores.
    project, outside = linked
    _install_cli(outside, tmp_path)
    _install_as_typed(monkeypatch, project, profile)
    assert (outside / ".apothem" / "memory").is_dir()

    result = _cli(
        "uninstall", "--harness", "cursor", "--project", str(outside), "--yes"
    )

    assert result.exit_code == 0, result.output
    for store in ("memory", "contexts", "learning"):
        assert not (outside / ".apothem" / store).exists(), store


def test_a_case_only_sibling_keeps_a_data_home_both_use(
    tmp_path: Path, profile: dict[str, Any]
) -> None:
    # Both installs keep their stores in the user home. Uninstalling proj
    # keeps them for Proj and names Proj as the install that holds them.
    shared = tmp_path / "prof-home" / "profile.yaml"
    shared.parent.mkdir()
    workspace = {**profile.get("workspace", {}), "scope": "user-home"}
    shared.write_bytes(yaml.safe_dump({**profile, "workspace": workspace}).encode())
    folder = tmp_path / "cs"
    case_sensitive_folder(folder)
    upper, lower = folder / "Proj", folder / "proj"
    for project in (upper, lower):
        project.mkdir()
        _install_cli(project, tmp_path, shared)
    stores = Path.home() / ".apothem"
    assert (stores / "memory").is_dir()

    run = CursorAdapter().uninstall(project=lower.resolve())

    (kept,) = [r for r in run.results if r.operation == "remove_data_home"]
    assert kept.outcome == "unchanged", kept.message
    assert str(upper.resolve()) in kept.message
    assert str(lower.resolve()) not in kept.message
    assert (stores / "memory").is_dir()


def test_a_case_only_sibling_keeps_its_own_data_stores_apart(
    tmp_path: Path, case_pair: tuple[Path, Path]
) -> None:
    # Each project keeps its stores in its own folder: uninstalling proj
    # removes proj's, and Proj's stay.
    upper, lower = case_pair
    _install_cli(lower, tmp_path)

    run = CursorAdapter().uninstall(project=lower.resolve())

    assert not run.errors, [error.message for error in run.errors]
    for store in ("memory", "contexts", "learning"):
        assert not (lower / ".apothem" / store).exists(), store
        assert (upper / ".apothem" / store).is_dir(), store


def test_a_case_only_copy_with_no_record_gets_no_notes(
    case_pair: tuple[Path, Path],
) -> None:
    # proj is a copy of the installed Proj, with no record of its own. The
    # notes about shared folders describe proj's install, of which there is
    # none, never Proj's.
    upper, lower = case_pair
    shutil.rmtree(lower)
    shutil.copytree(upper, lower)

    result = _cli("uninstall", "--harness", "cursor", "--project", str(lower), "--yes")

    # No record matches proj, so the uninstall does not finish (exit 2); its
    # only note is the no-record one, never a retention note about Proj's.
    assert result.exit_code == 2, result.output
    notes = [line for line in result.output.splitlines() if "Note:" in line]
    assert all("no install record matched" in note for note in notes), notes
    assert "still used by" not in result.output, result.output
    assert "no other Apothem install uses it" not in result.output, result.output
    assert CursorAdapter().verify(project=upper.resolve())


@pytest.mark.skipif(sys.platform != "win32", reason="admin shares are Windows paths")
def test_an_install_through_the_local_share_keeps_the_folder_removable(
    tmp_path: Path, profile: dict[str, Any]
) -> None:
    # An install spelled \\localhost\C$\X, of a folder installed as C:\X,
    # must not move the record to the share spelling, which a lookup of
    # C:\X never finds again.
    folder = (tmp_path / "X").resolve()
    folder.mkdir()
    _install_cli(folder, tmp_path)
    share = Path("\\\\localhost\\" + folder.drive[0] + "$" + str(folder)[2:])
    if not share.is_dir():
        pytest.skip("this host does not serve its drive as an admin share")

    _cli(
        "install",
        "--harness",
        "cursor",
        "--project",
        str(share),
        "--profile",
        str(tmp_path / "prof" / "profile.yaml"),
        "--yes",
    )
    result = _cli("uninstall", "--harness", "cursor", "--project", str(folder), "--yes")

    assert result.exit_code == 0, result.output
    assert "Uninstalled" in result.output, result.output
    assert _files(folder) == []
    for root in {record.root for record in install_ledger.read_records("cursor")}:
        assert install_ledger.active_install_records("cursor", root=root) == []
