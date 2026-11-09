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
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner, Result

from apothem.cli import main
from apothem.harnesses._shared import wrapper_factories
from apothem.harnesses.cursor import CursorAdapter
from apothem.harnesses.cursor.install import install as cursor_install
from apothem.harnesses.kimi_code.install import install as kimi_install
from apothem.harnesses.kimi_code.uninstall import uninstall as kimi_uninstall
from apothem.lib import install_ledger


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


def _install_as_typed(
    monkeypatch: pytest.MonkeyPatch, project: Path, profile: dict[str, Any]
) -> None:
    """Install through the API the way an earlier release did: as typed."""
    with monkeypatch.context() as patch:
        patch.setattr(wrapper_factories, "recorded_root", lambda _h, root: root)
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
        patch.setattr(wrapper_factories, "recorded_root", lambda _h, root: root)
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


def _install_cli(project: Path, tmp_path: Path) -> None:
    result = _cli(
        "install",
        "--harness",
        "cursor",
        "--project",
        str(project),
        "--profile",
        str(tmp_path / "prof" / "profile.yaml"),
        "--yes",
    )
    assert result.exit_code == 0, result.output


def _case_sensitive_folder(folder: Path) -> None:
    """Make *folder* tell ``Proj`` from ``proj``, or skip.

    On Windows the folder gets per-folder case sensitivity (as WSL sets it
    under ``/mnt/c``); elsewhere the file system must already be case
    sensitive.
    """
    folder.mkdir()
    if sys.platform == "win32":
        try:
            done = subprocess.run(
                ["fsutil", "file", "setCaseSensitiveInfo", str(folder), "enable"],
                capture_output=True,
                check=False,
            )
        except OSError:
            pytest.skip("fsutil is not available")
        if done.returncode != 0:
            pytest.skip("this host cannot turn on per-folder case sensitivity")
    (folder / "Probe").mkdir()
    if (folder / "probe").exists():
        pytest.skip("this file system does not tell names apart by case")
    (folder / "Probe").rmdir()


@pytest.fixture
def case_pair(tmp_path: Path, profile: dict[str, Any]) -> tuple[Path, Path]:
    """Return ``(Proj, proj)``: two folders whose names differ only in case.

    ``Proj`` holds a command-line install; ``proj`` holds a file of the
    user's own.
    """
    folder = tmp_path / "cs"
    _case_sensitive_folder(folder)
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

    assert install_ledger.recorded_root("cursor", lower) == lower.resolve()
    result = _cli("uninstall", "--harness", "cursor", "--project", str(lower), "--yes")

    assert result.exit_code == 0, result.output
    assert "Uninstalled" not in result.output, result.output
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

    assert result.exit_code == 0, result.output
    assert _files(folder / ".cursor" / "agents")
    assert not (folder / ".cursor" / "rules" / "apothem-rules.mdc").exists()
    if fmt == "json":
        rows = json.loads(result.output)["results"]
        assert [row["operation"] for row in rows] == ["uninstall"]
        assert rows[0]["outcome"] == "updated"
        assert rows[0]["detail"] == {"kept_reason": "no-record"}
        message = rows[0]["message"]
        assert message.startswith("no install record matched, so ")
        assert "Apothem's own lines in 2 files and its data folder were removed" in (
            message
        )
        assert "check that --project names the folder you installed into" in message
    else:
        text = " ".join(result.output.split())
        assert "Uninstalled" not in text
        assert "paths were kept: no install record shows Apothem wrote them" in text
        assert "Not uninstalled: cursor - no install record matched" in text


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

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["results"]
    assert rows[0]["outcome"] == "unchanged", rows
    assert rows[0]["detail"] == {"kept_reason": "no-record"}
    assert " removed" not in rows[0]["message"], rows[0]["message"]
    assert _files(folder) == installed
