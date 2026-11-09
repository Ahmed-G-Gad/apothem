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
