# SPDX-License-Identifier: MIT

"""``apothem.lib.home_write_guard`` sees every spelling of a protected folder.

A folder swapped for a link during a test (before or after the protected
folders were first resolved), a loopback admin share, a share reached by one of
the machine's own addresses, a device or long-path prefix, a short (8.3) name,
an alternate data stream, the macOS data-volume spelling, and a letter-case or
Unicode-normalization variant on a volume that ignores those all name the same
protected folder. Every home here
is a folder under ``tmp_path`` added with ``also_protect_home``; the string
checks of the Windows spellings touch no disk at all.
"""

from __future__ import annotations

import ntpath
import os
import socket
import sys
import time
import unicodedata
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from apothem.lib import atomic_io, clean_slate, home_write_guard


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


def _settled(folder: Path) -> None:
    """Date *folder* an hour back, like a home that has not changed lately."""
    past = time.time_ns() - 3600 * 10**9
    os.utime(folder, ns=(past, past))


@pytest.mark.parametrize("linked", [".config", ".claude"])
def test_a_home_folder_linked_after_a_check_protects_where_it_leads(
    fake_home: Path, tmp_path: Path, linked: str
) -> None:
    """The protected folders' resolved spellings follow the home as it is now."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    target = elsewhere / "apothem" / "x" if linked == ".config" else elsewhere / "x"
    _settled(fake_home)
    # These checks resolve the protected folders and keep them while the home
    # stays as it is.
    assert not home_write_guard.would_refuse(target)
    assert not home_write_guard.would_refuse(target)
    _link_folder(fake_home / linked, elsewhere)
    try:
        assert home_write_guard.would_refuse(target)
        with pytest.raises(home_write_guard.RealHomeWriteError):
            atomic_io.write_bytes_atomically(target, b"data")
        _settled(fake_home)
        assert home_write_guard.would_refuse(target)
    finally:
        _remove_folder_link(fake_home / linked)
    assert not home_write_guard.would_refuse(target)
    assert _everything_in(elsewhere) == []


def test_the_layout_changes_when_a_home_folder_becomes_a_link(
    fake_home: Path, tmp_path: Path
) -> None:
    _settled(fake_home)
    before, settled = home_write_guard._layout((str(fake_home),))
    assert settled
    _link_folder(fake_home / ".config", tmp_path / "elsewhere")
    try:
        after, settled_now = home_write_guard._layout((str(fake_home),))
    finally:
        _remove_folder_link(fake_home / ".config")
    assert after != before
    assert not settled_now


def test_a_folder_swapped_inside_a_linked_config_is_seen_at_once(
    fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``.config`` linked into a dotfiles folder: a change in there counts.

    With no settling time the resolved folders are reused whenever the layout
    is unchanged, so only a layout that reads the link's target sees the swap.
    """
    monkeypatch.setattr(home_write_guard, "_SETTLE_NS", 0)
    dotfiles = tmp_path / "dotfiles"
    (dotfiles / "apothem").mkdir(parents=True)
    third = tmp_path / "third"
    third.mkdir()
    _link_folder(fake_home / ".config", dotfiles)
    try:
        _settled(dotfiles)
        _settled(fake_home)
        assert home_write_guard.would_refuse(dotfiles / "apothem" / "x")
        assert not home_write_guard.would_refuse(third / "x")
        assert not home_write_guard.would_refuse(third / "x")
        (dotfiles / "apothem").rmdir()
        _link_folder(dotfiles / "apothem", third)
        try:
            assert home_write_guard.would_refuse(third / "x")
            with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
                atomic_io.write_bytes_atomically(third / "settings.yaml", b"data")
            assert caught.value.protected_root == str(fake_home / ".config" / "apothem")
        finally:
            _remove_folder_link(dotfiles / "apothem")
    finally:
        _remove_folder_link(fake_home / ".config")
    assert _everything_in(third) == []


def test_the_layout_reads_where_a_linked_config_leads(
    fake_home: Path, tmp_path: Path
) -> None:
    dotfiles = tmp_path / "dotfiles"
    _link_folder(fake_home / ".config", dotfiles)
    try:
        _settled(dotfiles)
        before, _ = home_write_guard._layout((str(fake_home),))
        (dotfiles / "opencode").mkdir()
        after, settled = home_write_guard._layout((str(fake_home),))
    finally:
        _remove_folder_link(fake_home / ".config")
    plain, _ = home_write_guard._layout((str(fake_home),))
    # The home, the link, and the folder the link leads to.
    assert len(before) == 3
    assert after != before
    assert not settled
    assert len(plain) == 2


# Short (8.3) names -----------------------------------------------------------


def _short_name(path: Path) -> str:
    """Return the short (8.3) spelling of *path*, or skip when it has none."""
    import ctypes

    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    short = buffer.value if length else ""
    if not short or ntpath.basename(short).lower() == path.name.lower():
        pytest.skip("this volume keeps no short (8.3) names")
    return short


@pytest.mark.skipif(sys.platform != "win32", reason="short names are Windows")
def test_a_short_name_in_the_last_part_is_refused(fake_home: Path) -> None:
    ledger = fake_home / ".apothem" / "ledger.jsonl"
    ledger.parent.mkdir()
    ledger.write_bytes(b"kept\n")
    short_root = _short_name(fake_home / ".apothem")
    short_home = _short_name(fake_home)
    assert home_write_guard.would_refuse(short_root)
    assert home_write_guard.would_refuse(short_root, tree=True)
    assert home_write_guard.would_refuse(short_home, tree=True)
    assert home_write_guard.would_refuse_project_root(short_home)
    with pytest.raises(home_write_guard.RealHomeWriteError):
        clean_slate._remove_path(Path(short_root))
    with pytest.raises(home_write_guard.RealHomeWriteError):
        clean_slate._remove_path(Path(short_home))
    assert ledger.read_bytes() == b"kept\n"


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
        # The NT object namespace, which a file call passes through as written.
        ("\\??\\C:\\Users\\me\\x", "C:\\Users\\me\\x"),
        ("/??/C:/Users/me/x", "C:\\Users\\me\\x"),
        ("\\??\\UNC\\localhost\\C$\\Users\\me\\x", "C:\\Users\\me\\x"),
        ("/??/unc/127.0.0.1/c$/x", "c:\\x"),
        ("C:\\Users\\me\\.apothem:evil", "C:\\Users\\me\\.apothem"),
        ("C:\\Users\\me\\.apothem:evil:$DATA", "C:\\Users\\me\\.apothem"),
        (
            "C:\\Users\\me\\.claude::$INDEX_ALLOCATION\\x",
            "C:\\Users\\me\\.claude\\x",
        ),
        ("\\\\localhost\\C$\\Users\\me\\.codex:s\\x", "C:\\Users\\me\\.codex\\x"),
        # The IPv6 loopback (::1), as Windows writes it in a UNC host.
        ("\\\\--1.ipv6-literal.net\\C$\\Users\\me\\x", "C:\\Users\\me\\x"),
        ("\\\\0--1.IPV6-LITERAL.NET\\c$\\x", "c:\\x"),
        ("\\\\0-0-0-0-0-0-0-1.ipv6-literal.net\\C$\\x", "C:\\x"),
        ("\\\\--1s1.ipv6-literal.net\\C$\\x", "C:\\x"),
        ("\\\\--ffff-7f00-1.ipv6-literal.net\\C$\\x", "C:\\x"),
        ("\\\\?\\UNC\\--1.ipv6-literal.net\\C$\\x", "C:\\x"),
        # Not this machine, not an admin share, or not a drive: left as written.
        ("\\\\--2.ipv6-literal.net\\C$\\x", "\\\\--2.ipv6-literal.net\\C$\\x"),
        (
            "\\\\fe80--1s5.ipv6-literal.net\\C$\\x",
            "\\\\fe80--1s5.ipv6-literal.net\\C$\\x",
        ),
        ("\\\\x.ipv6-literal.net\\C$\\x", "\\\\x.ipv6-literal.net\\C$\\x"),
        (
            "\\\\--1.ipv6-literal.net.example\\C$\\x",
            "\\\\--1.ipv6-literal.net.example\\C$\\x",
        ),
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
        _admin_share(fake_home, "--1.ipv6-literal.net"),
        "\\\\?\\UNC\\" + _admin_share(fake_home, "localhost")[2:],
        "\\\\.\\UNC\\" + _admin_share(fake_home, "127.0.0.1")[2:],
    ]
    for spelling in spellings:
        assert home_write_guard.would_refuse(f"{spelling}\\.claude\\x"), spelling
        assert home_write_guard.would_refuse(f"{spelling}\\.apothem"), spelling
        assert not home_write_guard.would_refuse(f"{spelling}\\notes.txt"), spelling
        assert home_write_guard.would_refuse(spelling, tree=True), spelling
    assert _everything_in(fake_home) == []


def _nt_spellings(folder: Path) -> list[str]:
    """Return *folder* behind the NT object-namespace prefix, in every form."""
    text = str(folder)
    unc = _admin_share(folder, "localhost")[2:]
    backslashed = [f"\\??\\{text}", f"\\??\\UNC\\{unc}", f"\\??\\unc\\{unc}"]
    return [
        *backslashed,
        *(spelling.replace("\\", "/") for spelling in backslashed),
        f"/??/{text}",
    ]


@pytest.mark.skipif(sys.platform != "win32", reason="the NT namespace is Windows")
def test_the_nt_object_namespace_prefix_is_refused(
    fake_home: Path, tmp_path: Path
) -> None:
    """``\\??\\`` reaches the plain path in a file call, so it is read first.

    ``os.path.abspath`` alone reads it as a folder ``??`` on the current drive,
    so none of these spellings matched before.
    """
    if not ntpath.splitdrive(str(fake_home))[0].endswith(":"):
        pytest.skip("the temporary folder is not on a drive letter")
    ledger = fake_home / ".apothem" / "state" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(b"kept\n")
    project = tmp_path / "project"
    project.mkdir()
    before = _everything_in(fake_home)
    for home in _nt_spellings(fake_home):
        sep = "/" if "/" in home[:4] else "\\"

        def under(*parts: str, home: str = home, sep: str = sep) -> str:
            return sep.join((home, *parts))

        assert home_write_guard.would_refuse(under(".apothem", "state")), home
        assert home_write_guard.would_refuse(
            under(".apothem", "state", "ledger.jsonl")
        ), home
        assert home_write_guard.would_refuse(
            under(".claude", "a", "b", "c", "settings.json")
        ), home
        assert home_write_guard.would_refuse(under(".config", "apothem")), home
        assert home_write_guard.would_refuse(under(".apothem"), tree=True), home
        assert home_write_guard.would_refuse(home, tree=True), home
        assert home_write_guard.would_refuse_project_root(home), home
        assert not home_write_guard.would_refuse(under("notes.txt")), home
        with pytest.raises(home_write_guard.RealHomeWriteError):
            home_write_guard.refuse_real_home_write(
                under(".claude", "x"), operation="write"
            )
        with pytest.raises(home_write_guard.RealHomeWriteError):
            home_write_guard.refuse_project_root_at_home(home, operation="install")
        with pytest.raises(home_write_guard.RealHomeWriteError):
            clean_slate._remove_path(Path(under(".apothem")))
    for spelling in _nt_spellings(project):
        assert not home_write_guard.would_refuse_project_root(spelling), spelling
    assert _everything_in(fake_home) == before


@pytest.mark.skipif(sys.platform != "win32", reason="the NT namespace is Windows")
@pytest.mark.parametrize("slash", ["\\", "/"])
def test_an_append_and_a_lock_through_the_nt_prefix_leave_the_home_alone(
    fake_home: Path, slash: str
) -> None:
    if not ntpath.splitdrive(str(fake_home))[0].endswith(":"):
        pytest.skip("the temporary folder is not on a drive letter")
    state = fake_home / ".apothem" / "state"
    state.mkdir(parents=True)
    ledger = state / "ledger.jsonl"
    ledger.write_bytes(b"kept\n")
    nt_state = f"\\??\\{state}".replace("\\", slash)
    with pytest.raises(home_write_guard.RealHomeWriteError):
        atomic_io.append_line_durably(Path(f"{nt_state}{slash}ledger.jsonl"), "x")
    with pytest.raises(home_write_guard.RealHomeWriteError):
        atomic_io.append_line_durably(Path(f"{nt_state}{slash}new.jsonl"), "x")
    with (
        pytest.raises(home_write_guard.RealHomeWriteError),
        atomic_io.advisory_lock(Path(f"{nt_state}{slash}x.install.lock")),
    ):
        pass
    with pytest.raises(home_write_guard.RealHomeWriteError):
        atomic_io.write_bytes_atomically(Path(f"{nt_state}{slash}x.json"), b"x")
    assert ledger.read_bytes() == b"kept\n"
    assert _everything_in(fake_home) == [fake_home / ".apothem", state, ledger]
    assert len(home_write_guard.drain_refusals()) == 4


def _reachable_share(home: Path, host: str) -> str:
    """Return *home* on the admin share of *host*, or skip when it cannot be reached."""
    unc_home = _admin_share(home, host)
    on_a_drive = ntpath.splitdrive(str(home))[0].endswith(":")
    if not on_a_drive or not Path(unc_home).is_dir():
        pytest.skip(f"the admin share of {host} is not reachable on this host")
    return unc_home


@pytest.mark.skipif(sys.platform != "win32", reason="admin shares are Windows")
@pytest.mark.parametrize("host", ["localhost", "--1.ipv6-literal.net"])
def test_a_write_through_the_loopback_admin_share_is_refused(
    fake_home: Path, host: str
) -> None:
    unc_home = _reachable_share(fake_home, host)
    target = Path(unc_home) / ".claude" / "settings.json"
    with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
        atomic_io.write_bytes_atomically(target, b"data")
    assert caught.value.protected_root == str(fake_home / ".claude")
    with pytest.raises(home_write_guard.RealHomeWriteError):
        atomic_io.append_line_durably(Path(unc_home) / ".apothem" / "x.log", "line")
    assert _everything_in(fake_home) == []


def _own_addresses() -> list[str]:
    """Return this machine's own IPv4 addresses, the loopback ones left out."""
    try:
        found = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    addresses = {str(item[4][0]) for item in found}
    return sorted(
        address for address in addresses if address and not address.startswith("127.")
    )


@pytest.mark.skipif(sys.platform != "win32", reason="admin shares are Windows")
def test_a_share_reached_by_one_of_this_machines_own_addresses_is_refused(
    fake_home: Path, tmp_path: Path
) -> None:
    """No string rule knows these hosts: the share is matched by file identity."""
    addresses = [
        address
        for address in _own_addresses()
        if Path(_admin_share(fake_home, address)).is_dir()
    ]
    if not addresses:
        pytest.skip("no admin share of this machine is reachable by its address")
    (tmp_path / "project").mkdir()
    for address in addresses:
        unc_home = _admin_share(fake_home, address)
        assert home_write_guard.would_refuse(f"{unc_home}\\.claude\\x"), address
        assert home_write_guard.would_refuse(f"{unc_home}\\.config\\apothem"), address
        assert home_write_guard.would_refuse(unc_home, tree=True), address
        assert not home_write_guard.would_refuse(f"{unc_home}\\notes.txt"), address
        assert home_write_guard.would_refuse_project_root(unc_home), address
        project = _admin_share(tmp_path / "project", address)
        assert not home_write_guard.would_refuse_project_root(project), address
        with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
            atomic_io.write_bytes_atomically(
                Path(unc_home) / ".claude" / "settings.json", b"data"
            )
        assert caught.value.protected_root == str(fake_home / ".claude")
    assert _everything_in(fake_home) == []


def _unused_drive() -> str:
    """Return a drive letter with nothing behind it, such as ``Q:``."""
    for letter in "QRSTUVWXYZ":
        if not Path(f"{letter}:\\").exists():
            return f"{letter}:"
    pytest.skip("every drive letter from Q to Z is in use")


def _as_drive(path: Path, drive: str) -> str:
    """Return *path* on *drive*, the rest of it unchanged."""
    return drive + ntpath.splitdrive(str(path))[1]


#: A share host no name service knows; every test that names it fakes the
#: file calls on it, so nothing goes to the network.
_FAKE_SHARE = "\\\\share-host.invalid\\data"


def _fake_share(
    monkeypatch: pytest.MonkeyPatch, local_drive: str
) -> list[tuple[str, str]]:
    """Serve :data:`_FAKE_SHARE` from *local_drive*, as a share of this machine.

    ``os.stat`` and ``os.lstat`` on the share read the local path, and the
    guard's ``_realpath`` leaves a share path as it is. Returns the share
    calls on it, in order, as ``(function, path)``.
    """
    asked: list[tuple[str, str]] = []
    real_stat, real_lstat = os.stat, os.lstat
    real_realpath = home_write_guard._realpath

    def local(name: str, path: object) -> object:
        text = os.fspath(path) if isinstance(path, (str, os.PathLike)) else None
        if isinstance(text, str) and text.lower().startswith(_FAKE_SHARE):
            asked.append((name, text))
            return local_drive + text[len(_FAKE_SHARE) :]
        return path

    def stat(path: object, *args: object, **kwargs: object) -> os.stat_result:
        return real_stat(local("stat", path), *args, **kwargs)

    def lstat(path: object, *args: object, **kwargs: object) -> os.stat_result:
        return real_lstat(local("lstat", path), *args, **kwargs)

    def realpath(path: str) -> str:
        if path.lower().startswith(_FAKE_SHARE):
            return path
        return real_realpath(path)

    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(os, "lstat", lstat)
    monkeypatch.setattr(home_write_guard, "_realpath", realpath)
    return asked


def _map_drive(monkeypatch: pytest.MonkeyPatch, drive: str, share_root: str) -> None:
    """Make the guard's ``_realpath`` read *drive* as *share_root*.

    That is what Windows does for a drive mapped to that share: the path
    resolves to its share spelling.
    """
    real_realpath = home_write_guard._realpath

    def realpath(path: str) -> str:
        if path[:2].lower() == drive.lower():
            return share_root + path[2:]
        return real_realpath(path)

    monkeypatch.setattr(home_write_guard, "_realpath", realpath)


@pytest.mark.skipif(sys.platform != "win32", reason="mapped drives are Windows")
def test_a_mapped_drive_that_resolves_to_a_share_is_refused(
    fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The resolved spelling of a drive mapped back to this machine is a share."""
    local_drive = ntpath.splitdrive(str(fake_home))[0]
    if not local_drive.endswith(":"):
        pytest.skip("the temporary folder is not on a drive letter")
    (fake_home / ".apothem" / "state").mkdir(parents=True)
    _fake_share(monkeypatch, local_drive)
    drive = _unused_drive()
    _map_drive(monkeypatch, drive, _FAKE_SHARE)
    mapped_home = _as_drive(fake_home, drive)
    assert home_write_guard.would_refuse(f"{mapped_home}\\.claude\\settings.json")
    assert home_write_guard.would_refuse(
        f"{mapped_home}\\.apothem\\state\\ledger.jsonl"
    )
    assert home_write_guard.would_refuse(mapped_home, tree=True)
    assert home_write_guard.would_refuse_project_root(mapped_home)
    assert not home_write_guard.would_refuse(f"{mapped_home}\\notes.txt")
    (tmp_path / "project").mkdir()
    assert not home_write_guard.would_refuse_project_root(
        _as_drive(tmp_path / "project", drive)
    )
    with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
        home_write_guard.refuse_real_home_write(
            f"{mapped_home}\\.claude\\x", operation="write"
        )
    assert caught.value.protected_root == str(fake_home / ".claude")


@pytest.mark.skipif(sys.platform != "win32", reason="shares are Windows")
@pytest.mark.parametrize("ledger", ["existing", "missing"])
def test_a_share_path_below_a_protected_folder_is_refused(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch, ledger: str
) -> None:
    """The nearest folder that exists is below ``.apothem``: walk up from it."""
    local_drive = ntpath.splitdrive(str(fake_home))[0]
    if not local_drive.endswith(":"):
        pytest.skip("the temporary folder is not on a drive letter")
    state = fake_home / ".apothem" / "state" / "codex"
    state.mkdir(parents=True)
    if ledger == "existing":
        (state / "ledger.jsonl").write_bytes(b"kept\n")
    _fake_share(monkeypatch, local_drive)
    share_state = _FAKE_SHARE + ntpath.splitdrive(str(state))[1]
    assert home_write_guard.would_refuse(f"{share_state}\\ledger.jsonl")
    assert home_write_guard.would_refuse(f"{share_state}\\a\\b\\c.lock")
    assert home_write_guard.would_refuse(share_state, tree=True)


@pytest.mark.skipif(sys.platform != "win32", reason="admin shares are Windows")
def test_reachable_own_address_shares_reach_the_backstop(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mapped drive to, and a path below a protected folder on, a real share."""
    addresses = [
        address
        for address in _own_addresses()
        if Path(_admin_share(fake_home, address)).is_dir()
    ]
    if not addresses:
        pytest.skip("no admin share of this machine is reachable by its address")
    state = fake_home / ".apothem" / "state"
    state.mkdir(parents=True)
    (state / "ledger.jsonl").write_bytes(b"kept\n")
    address = addresses[0]
    share_state = _admin_share(state, address)
    assert home_write_guard.would_refuse(f"{share_state}\\ledger.jsonl")
    assert home_write_guard.would_refuse(f"{share_state}\\new\\x.lock")
    drive = _unused_drive()
    local_drive = ntpath.splitdrive(str(fake_home))[0]
    _map_drive(monkeypatch, drive, f"\\\\{address}\\{local_drive[0]}$")
    mapped_home = _as_drive(fake_home, drive)
    assert home_write_guard.would_refuse(f"{mapped_home}\\.claude\\settings.json")
    assert home_write_guard.would_refuse_project_root(mapped_home)
    assert not home_write_guard.would_refuse(f"{mapped_home}\\notes.txt")
    with pytest.raises(home_write_guard.RealHomeWriteError):
        atomic_io.append_line_durably(Path(share_state) / "ledger.jsonl", "line")
    assert (state / "ledger.jsonl").read_bytes() == b"kept\n"


@pytest.mark.skipif(sys.platform != "win32", reason="shares are Windows")
def test_an_unreachable_share_is_asked_once_and_matches_nothing(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[tuple[str, str]] = []
    real_stat, real_lstat = os.stat, os.lstat
    remote = "\\\\remote-host.invalid\\share"

    def unreachable(name: str, real: Callable[..., object]) -> Callable[..., object]:
        def call(path: object, *args: object, **kwargs: object) -> object:
            text = os.fspath(path) if isinstance(path, (str, os.PathLike)) else None
            if isinstance(text, str) and text.lower().startswith(remote):
                asked.append((name, text))
                raise OSError(0, "The network path was not found", text, 53)
            return real(path, *args, **kwargs)

        return call

    monkeypatch.setattr(os, "stat", unreachable("stat", real_stat))
    monkeypatch.setattr(os, "lstat", unreachable("lstat", real_lstat))
    deep = f"{remote}\\proj\\a\\b\\c\\settings.json"
    project = f"{remote}\\proj"
    assert not home_write_guard.would_refuse(deep)
    assert not home_write_guard.would_refuse_project_root(project)
    # One lstat to resolve each path, whose error ends the resolving there, and
    # one stat to place it by identity, whose error ends the walk up the share.
    assert [(name, path.lower()) for name, path in asked] == [
        ("lstat", deep.lower()),
        ("stat", deep.lower()),
        ("lstat", project.lower()),
        ("stat", project.lower()),
    ]
    assert home_write_guard.refusals() == ()


@pytest.mark.skipif(sys.platform != "win32", reason="shares are Windows")
def test_each_share_folder_is_read_at_most_once_in_a_check(
    fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The written and resolved spellings share their folders' reads."""
    local_drive = ntpath.splitdrive(str(tmp_path))[0]
    if not local_drive.endswith(":"):
        pytest.skip("the temporary folder is not on a drive letter")
    asked = _fake_share(monkeypatch, local_drive)
    project = tmp_path / "project"
    (project / "real").mkdir(parents=True)
    on_share = _FAKE_SHARE + ntpath.splitdrive(str(project))[1]
    resolved = f"{on_share}\\real\\x\\y.json"
    real_realpath = home_write_guard._realpath

    def realpath(path: str) -> str:
        if path.lower().startswith(f"{on_share}\\link".lower()):
            return f"{on_share}\\real" + path[len(f"{on_share}\\link") :]
        return real_realpath(path)

    monkeypatch.setattr(home_write_guard, "_realpath", realpath)
    written = f"{on_share}\\link\\x\\y.json"
    assert not home_write_guard.would_refuse(written)
    stats = [path.lower() for name, path in asked if name == "stat"]
    assert written.lower() in stats
    assert resolved.lower() in stats
    assert f"{on_share}\\real".lower() in stats
    assert len(stats) == len(set(stats)), stats


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


# The macOS data volume ---------------------------------------------------------


@pytest.mark.parametrize(
    ("fold", "spelling", "expected"),
    [
        (False, "/System/Volumes/Data/Users/me/.claude", "/Users/me/.claude"),
        (False, "/System/Volumes/Data/Users/me", "/Users/me"),
        (False, "/System/Volumes/Data", "/"),
        (False, "/System/Volumes/Data/", "/"),
        (False, "/System/Volumes/DataX/Users/me", "/System/Volumes/DataX/Users/me"),
        (False, "/system/volumes/data/Users/me", "/system/volumes/data/Users/me"),
        (True, "/system/volumes/data/Users/me", "/Users/me"),
        (False, "/Users/me/System/Volumes/Data", "/Users/me/System/Volumes/Data"),
    ],
)
def test_the_macos_data_volume_reads_as_the_path_it_is_firmlinked_to(
    monkeypatch: pytest.MonkeyPatch, fold: bool, spelling: str, expected: str
) -> None:
    monkeypatch.setattr(home_write_guard, "_FOLD_CASE", fold)
    assert home_write_guard._data_volume_spelling(spelling) == expected


def test_the_data_volume_rule_is_on_for_macos_only_by_default() -> None:
    assert home_write_guard._DATA_VOLUME_FIRMLINK is (sys.platform == "darwin")


@pytest.mark.skipif(os.name == "nt", reason="the data volume is a macOS path")
@pytest.mark.parametrize("firmlink", [True, False])
def test_a_home_spelled_on_the_macos_data_volume_is_refused_there(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch, firmlink: bool
) -> None:
    """``/System/Volumes/Data/Users/<u>`` is ``/Users/<u>`` on macOS 10.15+."""
    monkeypatch.setattr(home_write_guard, "_DATA_VOLUME_FIRMLINK", firmlink)
    spelled = f"/System/Volumes/Data{fake_home}"
    assert home_write_guard.would_refuse(f"{spelled}/.claude/settings.json") is (
        firmlink
    )
    assert home_write_guard.would_refuse(f"{spelled}/.apothem") is firmlink
    assert home_write_guard.would_refuse(spelled, tree=True) is firmlink
    assert home_write_guard.would_refuse_project_root(spelled) is firmlink
    assert not home_write_guard.would_refuse(f"{spelled}/notes.txt")
    if firmlink:
        with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
            home_write_guard.refuse_real_home_write(
                f"{spelled}/.claude/x", operation="write"
            )
        assert caught.value.protected_root == str(fake_home / ".claude")
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


@pytest.mark.parametrize("written", ["NFC", "NFD"])
def test_a_home_in_the_other_unicode_form_is_refused_when_names_fold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, written: str
) -> None:
    """A macOS volume reads ``é`` as one character or as ``e`` and an accent."""
    monkeypatch.setattr(home_write_guard, "_FOLD_CASE", True)
    other = "NFD" if written == "NFC" else "NFC"
    home = tmp_path / unicodedata.normalize(written, "josé")
    home.mkdir()
    home_write_guard.also_protect_home(home)
    spelled = tmp_path / unicodedata.normalize(other, "JOSÉ")
    assert home_write_guard.would_refuse(spelled / ".claude" / "x")
    assert home_write_guard.would_refuse(spelled, tree=True)
    assert home_write_guard.would_refuse_project_root(spelled)
    assert not home_write_guard.would_refuse(tmp_path / "jose" / ".claude" / "x")
