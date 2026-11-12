# SPDX-License-Identifier: MIT

"""``install --clean`` refuses a home directory it cannot safely work under.

Every clean-slate target lies under the home, so the step stops before it
backs up or removes anything when the home is not a full path, is the root
of a drive or file system, leads to one through a link or a junction, or has
a link that loops. The loop tests make a real loop, a symbolic link pair or
a junction pair, and are skipped on a host that can make neither. The tests
that patch ``Path.resolve`` always run: they raise what Python 3.10 to 3.12
raise on a POSIX loop (``RuntimeError``) and what a strict resolve raises
from 3.13 on (``OSError`` with ``ELOOP``), and check that any other error of
a strict resolve does not refuse the home. No run here reaches a real root:
every backup and removal fails the test.
"""

from __future__ import annotations

import errno
import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.lib import clean_slate

_PROFILE = b"identity:\n  name: Ada Lovelace\n  email: ada@example.invalid\n"


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


def _loop(first: Path, second: Path) -> None:
    """Make *first* and *second* lead to each other, or skip the test."""
    first.parent.mkdir(parents=True, exist_ok=True)
    try:
        first.symlink_to(second, target_is_directory=True)
        second.symlink_to(first, target_is_directory=True)
        return
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot make a symbolic link")
        if first.is_symlink():
            first.unlink()
    try:
        import _winapi

        second.mkdir()
        _winapi.CreateJunction(str(second), str(first))
        second.rmdir()
        _winapi.CreateJunction(str(first), str(second))
    except OSError:
        pytest.skip("this host can make neither a symbolic link nor a junction")


def _forbid_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any backup or removal fail the test, so no run reaches a real root."""

    def refuse(*_args: object, **_kwargs: object) -> object:
        pytest.fail("clean slate went past its home check")

    monkeypatch.setattr(clean_slate, "_backup_targets", refuse)
    monkeypatch.setattr(clean_slate, "_remove_path", refuse)


def _home_leads_to_its_root(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    """Make *home* resolve to the root of its drive, as a link to it would."""
    real_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        return Path(self.anchor) if self == home else real_resolve(self, strict)

    monkeypatch.setattr(Path, "resolve", resolve)


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
    _home_leads_to_its_root(monkeypatch, home)

    with pytest.raises(clean_slate.UnsafeHomeError, match="leads to"):
        clean_slate.run_clean_slate(
            home, assume_yes=True, backup_root=tmp_path / "backups"
        )


def test_clean_slate_refuses_a_home_that_is_a_link_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A real loop: on Windows and on Python 3.13 and later the default
    # resolve returns it without raising, so only a strict one finds it.
    _forbid_changes(monkeypatch)
    home, other = tmp_path / "loop-a", tmp_path / "loop-b"
    _loop(home, other)

    with pytest.raises(clean_slate.UnsafeHomeError, match="cannot be followed"):
        clean_slate.run_clean_slate(home, dry_run=True)


@pytest.mark.parametrize(
    "failure",
    [RuntimeError("Symlink loop"), OSError(errno.ELOOP, "Too many levels")],
    ids=["runtime-error", "eloop"],
)
def test_clean_slate_refuses_a_home_whose_links_cannot_be_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    # Python 3.10 to 3.12 raise RuntimeError on a POSIX loop; 3.13 and later
    # raise OSError(ELOOP) from a strict resolve.
    _forbid_changes(monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    real_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        if self == home:
            raise failure
        return real_resolve(self, strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(clean_slate.UnsafeHomeError, match="cannot be followed"):
        clean_slate.run_clean_slate(home, dry_run=True)


@pytest.mark.parametrize(
    "failure",
    [PermissionError(errno.EACCES, "Access is denied"), OSError(22, "", None, 1)],
    ids=["access-denied", "invalid-function"],
)
def test_clean_slate_runs_when_a_strict_resolve_fails_for_another_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    # A home the strict resolve cannot read (a parent the user cannot list,
    # a volume that cannot report the final path: Windows error 1) is not a
    # link loop, so it is followed the default way and the run goes ahead.
    _forbid_changes(monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    real_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        if self == home and strict:
            raise failure
        return real_resolve(self, strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    result = clean_slate.run_clean_slate(home, dry_run=True)

    assert result.dry_run
    assert not result.removed


def test_clean_slate_runs_for_a_home_that_does_not_exist_yet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_changes(monkeypatch)

    result = clean_slate.run_clean_slate(tmp_path / "new-home", dry_run=True)

    assert result.dry_run
    assert not result.removed


def test_clean_slate_refuses_a_home_that_is_not_a_full_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Path("") is Path("."), so an empty home lands here too: it names a
    # folder only from where the command runs, and is not a drive root.
    _forbid_changes(monkeypatch)

    for home in (Path(), Path("relative-home")):
        with pytest.raises(clean_slate.UnsafeHomeError, match="not a full path"):
            clean_slate.run_clean_slate(home, dry_run=True)


# --- the CLI's error and fix ----------------------------------------------------


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    _spell_home(monkeypatch, folder)
    return folder


def _spell_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def _install_clean(tmp_path: Path) -> dict[str, object]:
    """Run ``install --clean --yes --format json``; return its error, which must exist."""
    profile = tmp_path / "profile.yaml"
    profile.write_bytes(_PROFILE)
    result = CliRunner().invoke(
        main,
        [
            "install",
            "--harness",
            "claude-code",
            "--profile",
            str(profile),
            "--clean",
            "--yes",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 1, result.output
    error = json.loads(result.output)["error"]
    assert isinstance(error, dict)
    assert error["code"] == "clean_slate.refused", error
    fix = str(error["fix"])
    assert "HOME, or USERPROFILE on Windows" in fix
    assert "full path of your own folder" in fix
    assert "interactively" not in fix
    return error


def test_install_clean_gives_the_home_fix_for_a_home_that_leads_to_a_root(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_changes(monkeypatch)
    _home_leads_to_its_root(monkeypatch, home)

    error = _install_clean(tmp_path)

    assert "leads to" in str(error["reason"])


def test_install_clean_gives_the_home_fix_for_a_home_that_is_a_link_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_changes(monkeypatch)
    home, other = tmp_path / "loop-a", tmp_path / "loop-b"
    _loop(home, other)
    _spell_home(monkeypatch, home)

    error = _install_clean(tmp_path)

    assert "cannot be followed" in str(error["reason"])


def test_install_clean_gives_the_home_fix_for_an_empty_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The home Python reports is empty: the run stops at the home check, in
    # a working folder of its own, before it looks anything up there.
    _forbid_changes(monkeypatch)
    monkeypatch.chdir(tmp_path)
    run_clean_slate = clean_slate.run_clean_slate

    def from_empty_home(_home: Path, **kwargs: object) -> object:
        return run_clean_slate(Path(), **kwargs)

    monkeypatch.setattr(
        "apothem.cli._clean_slate_phase.run_clean_slate", from_empty_home
    )

    error = _install_clean(tmp_path)

    assert "not a full path" in str(error["reason"])


def test_install_clean_checks_the_home_before_it_creates_the_profile(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No --profile: the default profile lies under the home, so the home is
    # refused before the starter profile is written there.
    _forbid_changes(monkeypatch)
    profile = home / ".config" / "apothem" / "profile.yaml"
    monkeypatch.setattr("apothem.lib.profile.DEFAULT_PROFILE_PATH", profile)
    _home_leads_to_its_root(monkeypatch, home)

    result = CliRunner().invoke(
        main,
        ["install", "--harness", "claude-code", "--clean", "--yes", "--format", "json"],
    )

    assert result.exit_code == 1, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "clean_slate.refused", error
    assert "leads to" in str(error["reason"])
    assert "HOME, or USERPROFILE on Windows" in str(error["fix"])
    assert not profile.exists()
