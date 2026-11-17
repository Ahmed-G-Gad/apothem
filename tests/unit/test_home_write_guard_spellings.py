# SPDX-License-Identifier: MIT

"""``apothem.lib.home_write_guard`` sees every spelling of a protected folder.

A folder swapped for a link during a test, a loopback admin share, a device
or long-path prefix, an alternate data stream, and a letter-case variant on a
case-insensitive volume all name the same protected folder. Every home here is
a folder under ``tmp_path`` added with ``also_protect_home``; the string checks
of the Windows spellings touch no disk at all.
"""

from __future__ import annotations

import ntpath
import os
import socket
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from apothem.lib import atomic_io, home_write_guard


@pytest.fixture(autouse=True)
def _forget_fake_homes() -> Iterator[None]:
    """Drop the added homes and the refusals each test logged."""
    yield
    home_write_guard.clear_extra_homes()
    home_write_guard.drain_refusals()


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """Return an empty folder protected as an account home."""
    home = tmp_path / "account-home"
    home.mkdir()
    home_write_guard.also_protect_home(home)
    return home


def _everything_in(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*"))


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a folder link to *target*, or skip when the host cannot."""
    target.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot create a folder link")
        import _winapi

        try:
            _winapi.CreateJunction(str(target), str(link))
        except OSError as exc:
            pytest.skip(f"this host cannot create a junction: {exc}")


def _remove_folder_link(link: Path) -> None:
    """Remove the link *link* itself, never what it leads to."""
    try:
        link.rmdir()  # a junction, or a folder symlink on Windows
    except OSError:
        link.unlink()  # a symlink on POSIX


# A folder that changes during a test ----------------------------------------


@pytest.mark.parametrize("before", ["missing", "plain"])
def test_a_folder_swapped_for_a_link_into_the_home_is_refused(
    fake_home: Path, tmp_path: Path, before: str
) -> None:
    swap = tmp_path / "swap"
    if before == "plain":
        swap.mkdir()
    target = swap / "settings.json"
    assert not home_write_guard.would_refuse(target)
    home_write_guard.refuse_real_home_write(target, operation="write")
    if before == "plain":
        swap.rmdir()
    _link_folder(swap, fake_home / ".claude")
    assert home_write_guard.would_refuse(target)
    with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
        atomic_io.write_bytes_atomically(target, b"data")
    assert caught.value.protected_root == str(fake_home / ".claude")
    assert _everything_in(fake_home / ".claude") == []


def test_a_link_that_becomes_a_plain_folder_is_allowed_again(
    fake_home: Path, tmp_path: Path
) -> None:
    swap = tmp_path / "swap"
    target = swap / "settings.json"
    _link_folder(swap, fake_home / ".claude")
    assert home_write_guard.would_refuse(target)
    with pytest.raises(home_write_guard.RealHomeWriteError):
        atomic_io.write_bytes_atomically(target, b"data")
    _remove_folder_link(swap)
    swap.mkdir()
    assert not home_write_guard.would_refuse(target)
    atomic_io.write_bytes_atomically(target, b"data")
    assert target.read_bytes() == b"data"
    assert _everything_in(fake_home / ".claude") == []


# Windows spellings, as strings -----------------------------------------------


@pytest.mark.parametrize(
    ("spelling", "expected"),
    [
        ("C:\\Users\\me\\.claude\\x", "C:\\Users\\me\\.claude\\x"),
        ("\\\\?\\C:\\Users\\me\\x", "C:\\Users\\me\\x"),
        ("\\\\.\\C:\\Users\\me\\x", "C:\\Users\\me\\x"),
        ("\\\\localhost\\C$\\Users\\me\\x", "C:\\Users\\me\\x"),
        ("\\\\LocalHost\\c$\\Users\\me\\x", "c:\\Users\\me\\x"),
        ("\\\\localhost\\C$", "C:\\"),
        ("\\\\localhost\\C$\\", "C:\\"),
        ("\\\\127.0.0.1\\C$\\Users\\me\\x", "C:\\Users\\me\\x"),
        ("\\\\127.45.6.7\\D$\\x", "D:\\x"),
        ("\\\\?\\UNC\\localhost\\C$\\Users\\me\\x", "C:\\Users\\me\\x"),
        ("\\\\?\\unc\\127.0.0.1\\c$\\Users\\me\\x", "c:\\Users\\me\\x"),
        ("\\\\.\\UNC\\localhost\\C$\\Users\\me\\x", "C:\\Users\\me\\x"),
        ("//localhost/C$/Users/me/x", "C:\\Users\\me\\x"),
        ("C:\\Users\\me\\.apothem:evil", "C:\\Users\\me\\.apothem"),
        ("C:\\Users\\me\\.apothem:evil:$DATA", "C:\\Users\\me\\.apothem"),
        (
            "C:\\Users\\me\\.claude::$INDEX_ALLOCATION\\x",
            "C:\\Users\\me\\.claude\\x",
        ),
        ("\\\\localhost\\C$\\Users\\me\\.codex:s\\x", "C:\\Users\\me\\.codex\\x"),
        # Not this machine, not an admin share, or not a drive: left as written.
        ("\\\\fileserver\\C$\\Users\\me\\x", "\\\\fileserver\\C$\\Users\\me\\x"),
        ("\\\\localhost\\share\\x", "\\\\localhost\\share\\x"),
        ("\\\\localhost\\CD$\\x", "\\\\localhost\\CD$\\x"),
        ("\\\\128.0.0.1\\C$\\x", "\\\\128.0.0.1\\C$\\x"),
        ("\\\\localhost.example\\C$\\x", "\\\\localhost.example\\C$\\x"),
    ],
)
def test_each_windows_spelling_reads_as_the_drive_letter_path(
    spelling: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(home_write_guard, "_machine_names", frozenset)
    assert home_write_guard._windows_spelling(spelling) == expected


@pytest.mark.parametrize("prefix", ["", "\\\\?\\UNC\\", "\\\\.\\UNC\\"])
def test_this_machines_own_name_is_a_loopback_host(
    monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    lead = prefix or "\\\\"
    names = home_write_guard._machine_names()
    assert socket.gethostname().lower() in names
    for name in names:
        for written in (name, name.upper()):
            spelling = f"{lead}{written}\\C$\\Users\\me\\x"
            assert home_write_guard._windows_spelling(spelling) == "C:\\Users\\me\\x"
    monkeypatch.setattr(
        home_write_guard,
        "_machine_names",
        lambda: frozenset({"build-box", "build-box.corp.example"}),
    )
    for host in ("BUILD-BOX", "build-box.corp.example"):
        spelling = f"{lead}{host}\\E$\\x"
        assert home_write_guard._windows_spelling(spelling) == "E:\\x"


def test_the_machine_names_need_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a host name lookup went to the network")

    for name in ("getfqdn", "gethostbyname", "gethostbyaddr", "getaddrinfo"):
        monkeypatch.setattr(socket, name, no_network)
    assert home_write_guard._machine_names()
    assert (
        home_write_guard._windows_spelling("\\\\elsewhere\\C$\\x")
        == "\\\\elsewhere\\C$\\x"
    )


def _admin_share(path: Path, host: str) -> str:
    drive, rest = ntpath.splitdrive(str(path))
    return f"\\\\{host}\\{drive[0]}${rest}"


@pytest.mark.skipif(sys.platform != "win32", reason="these spellings are Windows")
def test_every_windows_spelling_of_a_protected_folder_is_refused(
    fake_home: Path,
) -> None:
    home = str(fake_home)
    if not ntpath.splitdrive(home)[0].endswith(":"):
        pytest.skip("the temporary folder is not on a drive letter")
    spellings = [
        f"\\\\?\\{home}",
        f"\\\\.\\{home}",
        _admin_share(fake_home, "localhost"),
        _admin_share(fake_home, "LOCALHOST"),
        _admin_share(fake_home, "127.0.0.1"),
        _admin_share(fake_home, socket.gethostname()),
        "\\\\?\\UNC\\" + _admin_share(fake_home, "localhost")[2:],
        "\\\\.\\UNC\\" + _admin_share(fake_home, "127.0.0.1")[2:],
    ]
    for spelling in spellings:
        assert home_write_guard.would_refuse(f"{spelling}\\.claude\\x"), spelling
        assert home_write_guard.would_refuse(f"{spelling}\\.apothem"), spelling
        assert not home_write_guard.would_refuse(f"{spelling}\\notes.txt"), spelling
        assert home_write_guard.would_refuse(spelling, tree=True), spelling
    assert _everything_in(fake_home) == []


@pytest.mark.skipif(sys.platform != "win32", reason="admin shares are Windows")
def test_a_write_through_the_loopback_admin_share_is_refused(
    fake_home: Path,
) -> None:
    unc_home = _admin_share(fake_home, "localhost")
    on_a_drive = ntpath.splitdrive(str(fake_home))[0].endswith(":")
    if not on_a_drive or not Path(unc_home).is_dir():
        pytest.skip("\\\\localhost\\C$ is not reachable on this host")
    target = Path(unc_home) / ".claude" / "settings.json"
    with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
        atomic_io.write_bytes_atomically(target, b"data")
    assert caught.value.protected_root == str(fake_home / ".claude")
    with pytest.raises(home_write_guard.RealHomeWriteError):
        atomic_io.append_line_durably(Path(unc_home) / ".apothem" / "x.log", "line")
    assert _everything_in(fake_home) == []


@pytest.mark.skipif(sys.platform != "win32", reason="data streams are NTFS")
def test_an_alternate_data_stream_of_a_protected_folder_is_refused(
    fake_home: Path,
) -> None:
    home = str(fake_home)
    for spelling in (
        f"{home}\\.apothem:evil",
        f"{home}\\.apothem:evil:$DATA",
        f"{home}\\.claude::$INDEX_ALLOCATION\\x",
        f"{home}\\.config:s\\apothem\\profile.yaml",
    ):
        assert home_write_guard.would_refuse(spelling), spelling
    with pytest.raises(home_write_guard.RealHomeWriteError):
        atomic_io.write_bytes_atomically(Path(f"{home}\\.apothem:evil"), b"data")
    assert not home_write_guard.would_refuse(f"{home}\\notes.txt:stream")
    assert _everything_in(fake_home) == []


# Letter case -----------------------------------------------------------------


def test_letter_case_folds_on_macos_only_by_default() -> None:
    assert home_write_guard._FOLD_CASE is (sys.platform == "darwin")


@pytest.mark.parametrize("fold", [True, False])
def test_a_different_case_spelling_is_refused_when_case_folds(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch, fold: bool
) -> None:
    monkeypatch.setattr(home_write_guard, "_FOLD_CASE", fold)
    other_case = fake_home.parent / fake_home.name.upper() / ".CLAUDE" / "x"
    # Windows folds through normcase whatever the flag says; elsewhere only the
    # flag folds, since a case-sensitive Linux volume holds two folders here.
    expected = fold or os.name == "nt"
    assert home_write_guard.would_refuse(other_case) is expected
    assert home_write_guard.would_refuse(fake_home / ".claude" / "x")
    assert (
        home_write_guard.would_refuse_project_root(fake_home.parent / "ACCOUNT-HOME")
        is expected
    )
    if expected:
        with pytest.raises(home_write_guard.RealHomeWriteError):
            home_write_guard.refuse_real_home_write(other_case, operation="write")
