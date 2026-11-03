# SPDX-License-Identifier: MIT

"""A ``~/.config`` that is a link, as dotfile managers make it.

The write guard follows a link at ``~/.config`` for an install root below it,
OpenCode's folder or a ``CODEX_HOME`` there, when the link stays inside the
home. It still refuses a link that leaves the home, and a link at or below
the install root. Creating a symbolic link needs a privilege some Windows
hosts lack, so there each link is a junction, and the guard is shown it as a
link: ``Path.is_symlink`` does not report a junction.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_pathsafety import _linkable_ancestors
from apothem.harnesses.codex import CodexAdapter
from apothem.harnesses.opencode import OpenCodeAdapter
from apothem.harnesses.opencode.materializer import config_root, instruction_entries
from apothem.lib import install_ledger
from apothem.lib.install_ledger import LedgerRecord


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    return folder


def _link(link: Path, target: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make *link* lead to *target*, and have the guard see it as a link."""
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            raise
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        real = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda self: (self == link and os.path.lexists(self)) or real(self),
        )


def _unlink(link: Path) -> None:
    """Remove the link *link*, not the folder it leads to."""
    if sys.platform == "win32":
        link.rmdir()  # a junction goes; the folder it leads to stays
    else:
        link.unlink()


def _instructions(root: Path) -> list[str]:
    config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
    entries: list[str] = config["instructions"]
    return entries


def _roots() -> set[str]:
    return {record.root for record in install_ledger.read_records("opencode")}


def test_opencode_installs_through_a_linked_config_folder(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = home / "dotfiles" / "config"
    _link(home / ".config", real, monkeypatch)
    adapter = OpenCodeAdapter()
    root = home / ".config" / "opencode"

    adapter.install({})
    adapter.update({})

    assert _instructions(real / "opencode") == instruction_entries()
    assert install_ledger.active_install_records("opencode", root=root)
    assert _roots() == {str(root)}
    adapter.uninstall()
    assert not (real / "opencode" / "opencode.json").exists()


def test_a_linked_config_folder_leaving_the_home_stops_the_install(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside, monkeypatch)

    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        OpenCodeAdapter().install({})

    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("below", ["opencode", "opencode/agents"])
def test_a_link_at_or_below_the_opencode_folder_still_stops_the_install(
    below: str, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The link leads inside ~/.config, so only the link check can stop it.
    target = home / ".config" / f"linked-{below.replace('/', '-')}"
    _link(home / ".config" / below, target, monkeypatch)

    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        OpenCodeAdapter().install({})

    assert list(target.iterdir()) == []


def test_a_codex_home_below_a_linked_config_folder_installs(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = home / "dotfiles" / "config"
    _link(home / ".config", real, monkeypatch)
    monkeypatch.setenv("CODEX_HOME", str(home / ".config" / "codex"))

    CodexAdapter().install({})

    assert (real / "codex" / "AGENTS.md").is_file()


@pytest.mark.parametrize("where", ["at the codex home", "outside the home"])
def test_a_codex_install_through_a_refused_link_leaves_nothing(
    where: str, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CODEX_HOME=~/.config makes the link the install root itself; a link
    # leaving the home is refused wherever it sits.
    if where == "at the codex home":
        real = home / "dotfiles" / "config"
        monkeypatch.setenv("CODEX_HOME", str(home / ".config"))
    else:
        real = tmp_path / "outside" / "config"
        monkeypatch.setenv("CODEX_HOME", str(home / ".config" / "codex"))
    _link(home / ".config", real, monkeypatch)

    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        CodexAdapter().install({})

    assert list(real.iterdir()) == []
    assert not (home / ".agents").exists()


def test_xdg_config_home_through_the_link_keeps_one_install(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # XDG_CONFIG_HOME=$HOME/.config is the common export. A fresh install takes
    # the folder the link leads to; later runs keep that spelling, with the
    # variable unset and after the link is gone.
    real = home / "dotfiles" / "config"
    _link(home / ".config", real, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    adapter = OpenCodeAdapter()

    adapter.install({})
    monkeypatch.delenv("XDG_CONFIG_HOME")
    adapter.update({})
    _unlink(home / ".config")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(real))
    adapter.update({})

    resolved = install_driver._normalized(real) / "opencode"
    assert _roots() == {str(resolved)}
    entries = _instructions(real / "opencode")
    assert len(entries) == len(set(entries)) == len(instruction_entries())


def test_an_install_recorded_under_both_spellings_keeps_the_first(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = home / "dotfiles" / "config"
    _link(home / ".config", real, monkeypatch)
    default = home / ".config" / "opencode"
    resolved = install_driver._normalized(real) / "opencode"
    for root in (resolved, default):
        install_ledger.append_record(
            LedgerRecord.create(harness="opencode", root=root, kind="install")
        )

    assert config_root() == default
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    assert config_root() == default


def test_an_unreadable_ledger_gives_the_configured_folder(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = home / "dotfiles" / "config"
    _link(home / ".config", real, monkeypatch)
    ledger = install_ledger.ledger_path("opencode")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("not a ledger record\n", encoding="utf-8")

    assert config_root() == home / ".config" / "opencode"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    assert config_root() == install_driver._normalized(real) / "opencode"


def test_a_record_through_a_link_leaving_the_home_is_not_followed(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # With XDG_CONFIG_HOME unset, a record under the folder the link leads to
    # would otherwise take the write out of the home without the guard
    # seeing the link.
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside, monkeypatch)
    resolved = install_driver._normalized(outside) / "opencode"
    install_ledger.append_record(
        LedgerRecord.create(harness="opencode", root=resolved, kind="install")
    )

    assert config_root() == home / ".config" / "opencode"
    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        OpenCodeAdapter().install({})
    assert list(outside.iterdir()) == []


def test_linkable_ancestors_name_config_only_for_a_root_below_it(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = home / ".config"
    real = home / "dotfiles" / "config"
    _link(config, real, monkeypatch)
    target = config / "opencode" / "opencode.json"
    floor = install_driver._normalized(config)

    assert _linkable_ancestors(target, floor) == [config]
    assert _linkable_ancestors(home / ".codex" / "AGENTS.md", home) == []
    # CODEX_HOME=~/.config: the floor is above the folder the link leads to.
    assert _linkable_ancestors(config / "AGENTS.md", real.parent) == []

    _unlink(config)
    outside = tmp_path / "outside" / "config"
    _link(config, outside, monkeypatch)
    assert _linkable_ancestors(target, install_driver._normalized(config)) == []
