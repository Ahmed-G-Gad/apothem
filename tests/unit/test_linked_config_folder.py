# SPDX-License-Identifier: MIT

"""A ``~/.config`` that is a link, as dotfile managers make it.

The write guard follows a link at ``~/.config`` for an install root below it,
OpenCode's folder or a ``CODEX_HOME`` there, when the link stays inside the
home. It still refuses a link that leaves the home, and a link at or below
the install root. A link may take a write out of the home only where the
operator names the folder outside it through ``XDG_CONFIG_HOME``. Creating a
symbolic link needs a privilege some Windows hosts lack, so there each link
is a junction, which the guard also sees as a link; the cases that need a
symbolic link itself (a link loop) run on POSIX only.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver, install_driver_pathsafety
from apothem.harnesses._shared.install_driver_pathsafety import (
    _is_link,
    _linkable_ancestors,
    _unsafe_symlink,
)
from apothem.harnesses.codex import CodexAdapter
from apothem.harnesses.opencode import OpenCodeAdapter, materializer
from apothem.harnesses.opencode.materializer import config_root, instruction_entries
from apothem.lib import install_ledger
from apothem.lib.install_ledger import LedgerRecord

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows paths")
posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="needs a symbolic link, which needs a privilege"
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    return folder


def _link(link: Path, target: Path) -> None:
    """Make *link* lead to *target*: a symbolic link, or a junction on Windows."""
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            raise
        import _winapi

        _winapi.CreateJunction(str(target), str(link))


def _unlink(link: Path) -> None:
    """Remove the link *link*, not the folder it leads to."""
    if sys.platform == "win32":
        link.rmdir()  # a junction goes; the folder it leads to stays
    else:
        link.unlink()


def _instructions(root: Path) -> list[str]:
    config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
    entries: list[str] = config.get("instructions", [])
    return entries


def _roots() -> set[str]:
    return {record.root for record in install_ledger.read_records("opencode")}


def _files(folder: Path) -> list[Path]:
    return [path for path in folder.rglob("*") if path.is_file()]


def test_opencode_installs_through_a_linked_config_folder(home: Path) -> None:
    real = home / "dotfiles" / "config"
    _link(home / ".config", real)
    adapter = OpenCodeAdapter()
    root = home / ".config" / "opencode"

    adapter.install({})
    adapter.update({})

    assert _instructions(real / "opencode") == instruction_entries()
    assert install_ledger.active_install_records("opencode", root=root)
    assert _roots() == {str(root)}
    adapter.uninstall()
    assert not (real / "opencode" / "opencode.json").exists()


@pytest.mark.parametrize("xdg", ["unset", "~/.config", "~/xdg leading to ~/.config"])
def test_a_linked_config_folder_leaving_the_home_stops_the_install(
    xdg: str, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # XDG_CONFIG_HOME=$HOME/.config is the common export; spelled inside the
    # home, it names the folder through the same link and is refused with it.
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside)
    if xdg == "~/.config":
        monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    elif xdg != "unset":
        _link(home / "xdg", home / ".config")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))

    assert config_root() == home / ".config" / "opencode"
    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        OpenCodeAdapter().install({})

    assert _files(outside) == []
    assert _roots() == set()


def test_a_first_run_through_a_link_leaving_the_home_writes_nothing(
    home: Path, tmp_path: Path
) -> None:
    # The starter profile sits below ~/.config too: it is refused with the
    # install, before anything is written.
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside)

    result = CliRunner().invoke(main, ["install", "--harness", "opencode"])

    assert result.exit_code != 0
    assert "--profile PATH" in result.output
    assert _files(outside) == []


@pytest.mark.parametrize("spelling", ["xdg", "a/b"])
def test_an_xdg_config_home_in_the_home_leading_out_of_it_is_refused(
    spelling: str, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The variable is spelled inside the home, so the operator did not name
    # the folder outside it. With ~/a/b the link sits above the folder the
    # write guard's walk starts from.
    outside = tmp_path / "outside"
    _link(home / spelling.split("/")[0], outside)
    (home / spelling).mkdir(exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / spelling))

    assert config_root() == home / spelling / "opencode"
    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        OpenCodeAdapter().install({})
    with pytest.raises(install_driver.MaterializationError, match="uninstall refused"):
        OpenCodeAdapter().uninstall()

    assert _files(outside) == []


def test_xdg_config_home_spelled_outside_the_home_is_followed(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Naming the folder a ~/.config link leads to is the way to install
    # through a link that leaves the home.
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(outside))

    OpenCodeAdapter().install({})

    root = install_driver._normalized(outside) / "opencode"
    assert _roots() == {str(root)}
    assert _instructions(outside / "opencode") == instruction_entries()


def test_naming_the_link_target_after_a_default_install_keeps_one_set(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Installed while ~/.config was a folder; the folder then moved out of
    # the home behind a link, and XDG_CONFIG_HOME names where it went. The
    # entries the first install wrote name ~/.config/opencode, the same files.
    adapter = OpenCodeAdapter()
    adapter.install({})
    first = instruction_entries()
    outside = tmp_path / "outside" / "config"
    outside.parent.mkdir()
    (home / ".config").rename(outside)
    _link(home / ".config", outside)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(outside))

    adapter.install({})

    entries = _instructions(outside / "opencode")
    assert entries == instruction_entries()
    assert not set(entries) & set(first)
    adapter.uninstall()
    # The file the first install created goes, and so does its record.
    assert not (outside / "opencode" / "opencode.json").exists()
    for root in _roots():
        assert not install_ledger.active_install_records("opencode", root=root)


def test_replacing_the_link_with_a_folder_keeps_one_install(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = home / "dotfiles" / "config"
    _link(home / ".config", real)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    adapter = OpenCodeAdapter()

    adapter.install({})
    monkeypatch.delenv("XDG_CONFIG_HOME")
    adapter.update({})
    _unlink(home / ".config")
    real.rename(home / ".config")
    adapter.update({})

    root = home / ".config" / "opencode"
    assert _roots() == {str(root)}
    entries = _instructions(root)
    assert entries == instruction_entries()
    assert len(entries) == len(set(entries))


@pytest.mark.parametrize("below", ["opencode", "opencode/agents"])
def test_a_link_at_or_below_the_opencode_folder_still_stops_the_install(
    below: str, home: Path
) -> None:
    # The link leads inside ~/.config, so only the link check can stop it.
    target = home / ".config" / f"linked-{below.replace('/', '-')}"
    _link(home / ".config" / below, target)

    with pytest.raises(install_driver.MaterializationError, match="link"):
        OpenCodeAdapter().install({})

    assert list(target.iterdir()) == []


def test_a_codex_home_below_a_linked_config_folder_installs(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = home / "dotfiles" / "config"
    _link(home / ".config", real)
    monkeypatch.setenv("CODEX_HOME", str(home / ".config" / "codex"))

    CodexAdapter().install({})

    assert (real / "codex" / "AGENTS.md").is_file()


@pytest.mark.parametrize(
    "where", ["at the codex home", "outside the home", "codex home is the target"]
)
def test_a_codex_install_through_a_refused_link_leaves_nothing(
    where: str, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CODEX_HOME=~/.config makes the link the install root itself. A link
    # leaving the home is refused wherever it sits, and naming its target as
    # CODEX_HOME does not help: Codex also writes ~/.config/apothem.
    real = tmp_path / "outside" / "config"
    if where == "at the codex home":
        real = home / "dotfiles" / "config"
        monkeypatch.setenv("CODEX_HOME", str(home / ".config"))
    elif where == "outside the home":
        monkeypatch.setenv("CODEX_HOME", str(home / ".config" / "codex"))
    else:
        monkeypatch.setenv("CODEX_HOME", str(real / "codex"))
    _link(home / ".config", real)

    with pytest.raises(install_driver.MaterializationError):
        CodexAdapter().install({})

    assert _files(real) == []
    assert not (home / ".agents").exists()


def test_an_install_recorded_under_both_spellings_keeps_the_first(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = home / "dotfiles" / "config"
    _link(home / ".config", real)
    default = home / ".config" / "opencode"
    resolved = install_driver._normalized(real) / "opencode"
    for root in (resolved, default):
        install_ledger.append_record(
            LedgerRecord.create(harness="opencode", root=root, kind="install")
        )

    assert config_root() == default
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    assert config_root() == default


@pytest.mark.parametrize("ledger", ["readable", "not a record", "not UTF-8"])
def test_an_unreadable_ledger_holds_no_usable_record(
    ledger: str, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A readable record at the folder the link leads to is adopted; the same
    # record behind a bad line before it (not a torn final line) is not.
    real = home / "dotfiles" / "config"
    _link(home / ".config", real)
    resolved = install_driver._normalized(real) / "opencode"
    path = install_ledger.append_record(
        LedgerRecord.create(harness="opencode", root=resolved, kind="install")
    )
    prefix = {"readable": b"", "not a record": b"not a record\n"}.get(
        ledger, b"\xff\xfe\n"
    )
    path.write_bytes(prefix + path.read_bytes())
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    expected = resolved if ledger == "readable" else home / ".config" / "opencode"
    assert config_root() == expected
    roots = frozenset({str(resolved)}) if ledger == "readable" else frozenset()
    assert materializer._active_roots() == roots


def test_a_record_through_a_link_leaving_the_home_is_not_followed(
    home: Path, tmp_path: Path
) -> None:
    # With XDG_CONFIG_HOME unset, a record under the folder the link leads to
    # would otherwise take the write out of the home without the guard
    # seeing the link.
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside)
    for root in (
        install_driver._normalized(outside) / "opencode",
        home / ".config" / "opencode",
    ):
        install_ledger.append_record(
            LedgerRecord.create(harness="opencode", root=root, kind="install")
        )

    assert config_root() == home / ".config" / "opencode"
    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        OpenCodeAdapter().install({})
    assert _files(outside) == []


def test_config_root_never_raises(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Python 3.10-3.12 raise RuntimeError resolving a link loop.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))

    def loop(self: Path, strict: bool = False) -> Path:
        raise RuntimeError(f"Symlink loop from {self!r}")

    monkeypatch.setattr(Path, "resolve", loop)

    assert config_root() == home / ".config" / "opencode"


def _read_only_commands_exit_zero() -> None:
    runner = CliRunner()
    for args in (
        ["status"],
        ["doctor"],
        ["harnesses", "list"],
        ["verify", "--harness", "opencode"],
    ):
        result = runner.invoke(main, args)
        assert result.exception is None or isinstance(result.exception, SystemExit), (
            args,
            result.output,
        )
        # verify exits 1 when the harness is not installed; the others exit 0.
        allowed = (0, 1) if args[0] == "verify" else (0,)
        assert result.exit_code in allowed, (args, result.exit_code, result.output)
        assert "Traceback" not in result.output, args


def test_read_only_commands_survive_a_ledger_that_is_not_utf8(home: Path) -> None:
    ledger = install_ledger.ledger_path("opencode")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_bytes(b"\xff\xfe\x00not a ledger\n{}\n")

    assert config_root() == home / ".config" / "opencode"
    _read_only_commands_exit_zero()


@posix_only
def test_read_only_commands_survive_a_link_loop_at_the_config_folder(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (home / ".config").symlink_to(home / ".config-loop")
    (home / ".config-loop").symlink_to(home / ".config")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    assert config_root() == home / ".config" / "opencode"
    _read_only_commands_exit_zero()


def test_linkable_ancestors_name_config_only_for_a_root_below_it(
    home: Path, tmp_path: Path
) -> None:
    config = home / ".config"
    real = home / "dotfiles" / "config"
    _link(config, real)
    target = config / "opencode" / "opencode.json"
    floor = install_driver._normalized(config)

    assert _linkable_ancestors(target, floor) == [config]
    assert _linkable_ancestors(home / ".codex" / "AGENTS.md", home) == []
    # CODEX_HOME=~/.config: the floor is above the folder the link leads to.
    assert _linkable_ancestors(config / "AGENTS.md", real.parent) == []

    _unlink(config)
    outside = tmp_path / "outside" / "config"
    _link(config, outside)
    assert _linkable_ancestors(target, install_driver._normalized(config)) == []


@windows_only
def test_the_write_guard_sees_a_junction(home: Path, tmp_path: Path) -> None:
    import _winapi

    outside = tmp_path / "outside"
    outside.mkdir()
    (home / "file.txt").write_text("x", encoding="utf-8")
    _winapi.CreateJunction(str(outside), str(home / "junction"))

    assert _is_link(home / "junction")
    assert not _is_link(home)
    assert not _is_link(home / "file.txt")
    assert not _is_link(home / "missing")
    target = home / "junction" / "a" / "b.txt"
    assert _unsafe_symlink(target, install_driver._normalized(home / "junction")) == (
        home / "junction"
    )
    # A dangling junction is still a link in the path.
    outside.rmdir()
    assert _unsafe_symlink(target, home) == home / "junction"


@windows_only
def test_a_change_of_case_in_xdg_config_home_names_the_default_install(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (home / ".config").mkdir()
    adapter = OpenCodeAdapter()
    adapter.install({})
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config").upper())

    adapter.update({})

    root = home / ".config" / "opencode"
    assert _roots() == {str(root)}
    assert _instructions(root) == instruction_entries()

    # The same spelling through a junction leaving the home is refused.
    shutil.rmtree(home / ".config")
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside)
    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        adapter.update({})
    assert _files(outside) == []


def _short_name(path: Path) -> str:
    import ctypes

    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    return buffer.value if length else str(path)


@windows_only
@pytest.mark.parametrize("short", ["home", "xdg"])
def test_a_short_name_spelling_names_the_same_install(
    short: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "home folder with a long name"
    (folder / ".config").mkdir(parents=True)
    spelled = _short_name(folder)
    if os.path.normcase(spelled) == os.path.normcase(str(folder)):
        pytest.skip("this volume does not make short (8.3) names")
    home = spelled if short == "home" else str(folder)
    xdg = str(folder) if short == "home" else spelled
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("USERPROFILE", home)
    adapter = OpenCodeAdapter()

    adapter.install({})
    monkeypatch.setenv("XDG_CONFIG_HOME", str(Path(xdg) / ".config"))
    adapter.update({})

    assert _roots() == {str(Path(home) / ".config" / "opencode")}
    entries = _instructions(Path(home) / ".config" / "opencode")
    assert len(entries) == len(set(entries)) == len(instruction_entries())


@pytest.mark.parametrize(
    "command",
    [
        ["quickstart", "--harness", "opencode", "--yes"],
        ["profile", "init"],
        ["profile", "edit"],
    ],
)
def test_every_starter_profile_write_refuses_a_link_leaving_the_home(
    command: list[str], home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The starter profile sits below ~/.config, so each command that creates
    # it stops the way a first install does, before anything is written.
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside)
    monkeypatch.setattr("click.edit", _no_editor)

    result = CliRunner().invoke(main, command)

    assert "--profile PATH" in result.output, result.output
    assert "Created a starter profile" not in result.output
    assert _files(outside) == []


def _no_editor(**kwargs: object) -> None:
    del kwargs


def test_an_explicit_profile_path_outside_the_home_is_still_written(
    tmp_path: Path, home: Path
) -> None:
    profile = tmp_path / "elsewhere" / "profile.yaml"

    result = CliRunner().invoke(main, ["profile", "init", "--profile", str(profile)])

    assert result.exit_code == 0, result.output
    assert profile.is_file()


@pytest.mark.parametrize("depth", ["w/codex", "w/x/codex", "w/x/y/codex"])
def test_a_codex_home_below_a_link_leaving_the_home_is_refused(
    depth: str, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The write guard walks up only to the folder above CODEX_HOME, so a link
    # two or more levels up is found by the separate check.
    outside = tmp_path / "outside"
    _link(home / "w", outside)
    monkeypatch.setenv("CODEX_HOME", str(home / depth))

    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        CodexAdapter().install({})
    with pytest.raises(install_driver.MaterializationError, match="uninstall refused"):
        CodexAdapter().uninstall()

    assert _files(outside) == []


def test_a_codex_home_spelled_outside_the_home_is_followed(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "outside" / "codex"
    monkeypatch.setenv("CODEX_HOME", str(folder))

    CodexAdapter().install({})

    assert (folder / "AGENTS.md").is_file()


@pytest.mark.parametrize("harness", ["claude-code", "codex"])
def test_a_home_folder_that_is_itself_a_link_installs(
    harness: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A profile moved to another drive behind a junction (a symbolic link on
    # POSIX): every write still lands inside the home the link leads to.
    real = tmp_path / "real"
    linked = tmp_path / "linked"
    _link(linked, real)
    monkeypatch.setenv("HOME", str(linked))
    monkeypatch.setenv("USERPROFILE", str(linked))
    folder = ".claude" if harness == "claude-code" else ".codex"

    target = linked / folder / "x.txt"
    assert _unsafe_symlink(target, install_driver._normalized(linked)) is None
    result = CliRunner().invoke(main, ["install", "--harness", harness])

    assert result.exit_code == 0, result.output
    assert (real / folder).is_dir()


def test_a_bind_mount_of_the_home_is_not_reported_as_a_link(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Path.resolve does not see a bind mount (or a macOS firmlink), so the
    # spelling seems to leave the home although no link is on it.
    root = home / "cfg" / "opencode"
    root.mkdir(parents=True)
    monkeypatch.setattr(install_driver_pathsafety, "_within_allowed_root", _never)

    assert install_driver_pathsafety._link_leaving_home(root) is None
    install_driver_pathsafety.refuse_link_leaving_home(
        "opencode", root, operation="opencode_config"
    )


def _never(target: Path, root: Path) -> bool:
    del target, root
    return False


def test_a_failed_ledger_read_is_not_kept(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A scanner holding the file for a moment must not hide the record for the
    # rest of the process.
    real = home / "dotfiles" / "config"
    _link(home / ".config", real)
    resolved = install_driver._normalized(real) / "opencode"
    install_ledger.append_record(
        LedgerRecord.create(harness="opencode", root=resolved, kind="install")
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    read = install_ledger.read_records
    held = [True]

    def flaky(harness: str) -> list[LedgerRecord]:
        if held[0]:
            raise PermissionError("held by a scanner")
        return read(harness)

    monkeypatch.setattr(install_ledger, "read_records", flaky)
    materializer._ACTIVE_ROOTS.clear()

    assert config_root() == home / ".config" / "opencode"
    held[0] = False
    assert config_root() == resolved


@pytest.mark.parametrize("ledger", ["not UTF-8", "nested too deep"])
def test_a_ledger_that_cannot_be_parsed_is_read_once(
    ledger: str, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = install_ledger.ledger_path("opencode")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = b"\xff\xfe" if ledger == "not UTF-8" else b"[" * 200000 + b"]" * 200000
    path.write_bytes(body + b"\n{}\n")
    read = install_ledger.read_records
    calls: list[str] = []

    def counted(harness: str) -> list[LedgerRecord]:
        calls.append(harness)
        return read(harness)

    monkeypatch.setattr(install_ledger, "read_records", counted)
    materializer._ACTIVE_ROOTS.clear()

    for _ in range(3):
        assert materializer._active_roots() == frozenset()
        assert config_root() == home / ".config" / "opencode"
    assert materializer.install_notes(home / "xdg" / "opencode", {}) == []
    assert len(calls) == 1


def _move_config_out_of_the_home(home: Path, tmp_path: Path) -> Path:
    outside = tmp_path / "outside" / "config"
    outside.parent.mkdir(exist_ok=True)
    (home / ".config").rename(outside)
    _link(home / ".config", outside)
    return outside


def test_uninstalling_through_the_link_target_removes_the_default_install(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Installed while ~/.config was a folder; the folder then moved out of the
    # home behind a link. Uninstalling with XDG_CONFIG_HOME naming where it
    # went, without installing there first, removes that install.
    adapter = OpenCodeAdapter()
    adapter.install({})
    outside = _move_config_out_of_the_home(home, tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(outside))

    adapter.uninstall()

    config = outside / "opencode"
    assert not (config / "opencode.json").exists()
    assert not (config / install_driver.PROFILE_DOCUMENT_RELATIVE).exists()
    for root in _roots():
        assert not install_ledger.active_install_records("opencode", root=root)


def test_an_earlier_install_note_names_the_link_target(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # With ~/.config leading out of the home, an uninstall with
    # XDG_CONFIG_HOME unset is refused; the note says what works instead.
    adapter = OpenCodeAdapter()
    adapter.install({})
    outside = _move_config_out_of_the_home(home, tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))

    run = adapter.install({})

    notes = [r.message for r in run.results if r.outcome == "warning"]
    target = str(install_driver._normalized(outside))
    assert any("An earlier Apothem install" in n and target in n for n in notes)
    monkeypatch.setenv("XDG_CONFIG_HOME", target)
    adapter.uninstall()
    assert not (outside / "opencode" / "opencode.json").exists()


def test_a_record_from_before_ownership_loses_its_respelled_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The record names the home as the link leads to it; with HOME now spelled
    # through the link, the entries the earlier install wrote are respelled.
    real = tmp_path / "real"
    (real / ".config").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real))
    monkeypatch.setenv("USERPROFILE", str(real))
    adapter = OpenCodeAdapter()
    adapter.install({})
    path = install_ledger.ledger_path("opencode")
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        for target in record.get("targets", []):
            target.pop("owned", None)
        lines.append(json.dumps(record))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    linked = tmp_path / "linked"
    _link(linked, real)
    monkeypatch.setenv("HOME", str(linked))
    monkeypatch.setenv("USERPROFILE", str(linked))

    adapter.install({})

    entries = _instructions(real / ".config" / "opencode")
    assert len(entries) == len(set(entries)) == len(instruction_entries())
