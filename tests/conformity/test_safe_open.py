# SPDX-License-Identifier: MIT

"""The guarded open reads a project file one level at a time, never through a link.

Why these tests exist. Every ``--all`` validator and the ``--all-perwrite``
corpus run read project files through ``_safe_open``: the root is opened, then
each folder inside the folder opened before it, then the file, and no open
follows a link. These tests put each kind of entry (a real folder, a folder
link or junction, a file, a missing name, a named pipe, a file link) at each
level of a four-level path and check what the open does; they check that a
reparse point that is not a link (a cloud placeholder, a deduplicated file) is
read through its filter on Windows, reopened from its first handle and not by
name, that the text read matches ``Path.read_text``, and that no folder stays
open between reads, so a folder swapped for a link after one read is refused
at the next. They also check that the validators which count a swapped
file as missing report a file they cannot read for any other reason as
unreadable, rather than stopping with a traceback.
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
import socket
import stat
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from apothem.conformity import (
    _project_paths,
    _safe_open,
    cross_platform_matrix_grep,
    oidc_trusted_publishing_grep,
    plans_discipline_language_grep,
    smoke_install_grep,
    workflow_concurrency_grep,
)
from apothem.conformity._safe_open import (
    ProjectFileRefusedError,
    open_project_file,
    read_project_bytes,
    read_project_text,
)

# The path every level test reads: three folders, then the file.
_LEVELS = ("a", "b", "c", "f.txt")
_INSIDE = b"inside\n"
_OUTSIDE = b"outside\n"

_POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="named pipes exist only on POSIX systems"
)
_WINDOWS_ONLY = pytest.mark.skipif(sys.platform != "win32", reason="Windows opens")
_POSIX_OPENS = pytest.mark.skipif(sys.platform == "win32", reason="POSIX opens")


@pytest.fixture(autouse=True)
def _no_skip_log() -> Iterator[None]:
    """Leave no skip log behind for the next test."""
    yield
    _project_paths.take_skipped_paths()


def _tree(base: Path, content: bytes) -> Path:
    """Write ``a/b/c/f.txt`` holding *content* under *base*; return *base*."""
    target = base.joinpath(*_LEVELS)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return base


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a folder link to *target*: a junction on Windows."""
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        return
    link.symlink_to(target, target_is_directory=True)


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as exc:  # Windows without the symbolic-link privilege
        pytest.skip(f"cannot create a symbolic link here: {exc}")


def _remove_level(path: Path) -> None:
    """Delete the entry *path* and all below it."""
    if path.is_dir():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()
            else:
                child.unlink()
        path.rmdir()
    else:
        path.unlink()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project holding ``a/b/c/f.txt``, and an outside copy beside it."""
    _tree(tmp_path / "outside", _OUTSIDE)
    return _tree(tmp_path / "project", _INSIDE)


def _level(root: Path, depth: int) -> Path:
    return root.joinpath(*_LEVELS[: depth + 1])


def _target(root: Path) -> Path:
    return root.joinpath(*_LEVELS)


@pytest.mark.parametrize("depth", range(len(_LEVELS) - 1))
def test_a_folder_link_at_any_level_is_refused_and_noted(
    project: Path, depth: int
) -> None:
    """A folder link or junction in place of a folder is never followed."""
    level = _level(project, depth)
    _remove_level(level)
    _link_folder(level, _level(project.parent / "outside", depth))
    _project_paths.start_skip_log(project)

    with pytest.raises(ProjectFileRefusedError) as caught:
        read_project_bytes(project, _target(project))

    assert caught.value.errno == errno.ELOOP
    assert _project_paths.take_skipped_paths() == [
        level.relative_to(project).as_posix()
    ]


def test_a_file_link_is_refused_and_noted(project: Path) -> None:
    """A symbolic link in the file's place is never read through."""
    target = _target(project)
    target.unlink()
    _symlink_or_skip(target, _target(project.parent / "outside"))
    _project_paths.start_skip_log(project)

    with pytest.raises(ProjectFileRefusedError):
        read_project_bytes(project, target)

    assert _project_paths.take_skipped_paths() == ["a/b/c/f.txt"]


@pytest.mark.parametrize("depth", range(len(_LEVELS)))
def test_a_missing_level_is_file_not_found(project: Path, depth: int) -> None:
    _remove_level(_level(project, depth))
    _project_paths.start_skip_log(project)

    with pytest.raises(FileNotFoundError):
        read_project_bytes(project, _target(project))

    assert _project_paths.take_skipped_paths() == []


@pytest.mark.parametrize("depth", range(len(_LEVELS) - 1))
def test_a_file_in_a_folder_place_is_not_a_folder(project: Path, depth: int) -> None:
    level = _level(project, depth)
    _remove_level(level)
    level.write_bytes(b"a file\n")

    with pytest.raises(NotADirectoryError):
        read_project_bytes(project, _target(project))


def test_a_folder_in_the_file_place_is_a_folder(project: Path) -> None:
    target = _target(project)
    target.unlink()
    target.mkdir()

    with pytest.raises(IsADirectoryError):
        read_project_bytes(project, target)


@_POSIX_ONLY
@pytest.mark.parametrize("depth", range(len(_LEVELS)))
def test_a_named_pipe_at_any_level_is_never_waited_on(
    project: Path, depth: int
) -> None:
    """A named pipe is not opened as a file or a folder, never makes the read
    wait, and is noted at any level."""
    level = _level(project, depth)
    _remove_level(level)
    os.mkfifo(level)
    _project_paths.start_skip_log(project)

    with pytest.raises(ProjectFileRefusedError):
        read_project_bytes(project, _target(project))

    assert _project_paths.take_skipped_paths() == [
        level.relative_to(project).as_posix()
    ]


class _SwappingOs:
    """``os`` for ``_safe_open``, swapping one entry right after its look."""

    def __init__(self, name: str, swap: Callable[[], None]) -> None:
        self._name = name
        self._swap: Callable[[], None] | None = swap

    def __getattr__(self, attribute: str) -> Any:  # noqa: ANN401
        return getattr(os, attribute)

    def stat(self, path: Any, **kwargs: Any) -> os.stat_result:  # noqa: ANN401
        seen = os.stat(path, **kwargs)  # noqa: PTH116 - stands in for os.stat
        if path == self._name and self._swap is not None:
            swap, self._swap = self._swap, None
            swap()
        return seen


@_POSIX_ONLY
@pytest.mark.parametrize("depth", range(len(_LEVELS)))
def test_a_socket_swapped_in_after_the_look_is_refused_and_noted(
    project: Path, monkeypatch: pytest.MonkeyPatch, depth: int
) -> None:
    """``openat`` on a socket fails with ``ENXIO``; that is a swap too."""
    level = _level(project, depth)
    held: list[socket.socket] = []

    def swap() -> None:
        _remove_level(level)
        # A socket's path must be short: bind it by its name in its folder.
        monkeypatch.chdir(level.parent)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        held.append(server)
        server.bind(level.name)

    monkeypatch.setattr(_safe_open, "os", _SwappingOs(level.name, swap))
    _project_paths.start_skip_log(project)
    try:
        with pytest.raises(ProjectFileRefusedError):
            read_project_bytes(project, _target(project))
    finally:
        for server in held:
            server.close()

    assert held, "the look never reached the level"
    assert _project_paths.take_skipped_paths() == [
        level.relative_to(project).as_posix()
    ]


@_POSIX_ONLY
@pytest.mark.parametrize("depth", range(len(_LEVELS) - 1))
def test_a_file_swapped_in_for_a_folder_after_the_look_is_not_a_folder(
    project: Path, monkeypatch: pytest.MonkeyPatch, depth: int
) -> None:
    """A plain file is not a link: it is not a folder, and nothing is noted."""
    level = _level(project, depth)

    def swap() -> None:
        _remove_level(level)
        level.write_bytes(b"a file\n")

    monkeypatch.setattr(_safe_open, "os", _SwappingOs(level.name, swap))
    _project_paths.start_skip_log(project)

    with pytest.raises(NotADirectoryError):
        read_project_bytes(project, _target(project))

    assert _project_paths.take_skipped_paths() == []


@_POSIX_ONLY
@pytest.mark.skipif(
    not (hasattr(os, "O_PATH") or hasattr(os, "O_SEARCH")),
    reason="this system opens a folder only to read it",
)
@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="permissions do not apply to root",
)
def test_a_folder_that_can_be_searched_but_not_read_still_opens(
    project: Path,
) -> None:
    """A folder with search permission alone (``--x``) was enough to open a
    file below it by name, and is enough here."""
    folders = [project, *(_level(project, depth) for depth in range(3))]
    for folder in folders:
        folder.chmod(stat.S_IXUSR)
    try:
        data = read_project_bytes(project, _target(project))
    finally:
        for folder in folders:
            folder.chmod(stat.S_IRWXU)

    assert data == _INSIDE


@_POSIX_OPENS
def test_a_system_without_opens_inside_a_folder_fails_as_unreadable(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where ``openat`` or ``fstatat`` is missing, a read raises ``OSError``,
    which the validators handle, not ``NotImplementedError``."""
    monkeypatch.setattr(_safe_open, "_OPENS_INSIDE_A_FOLDER", False)

    with pytest.raises(OSError, match="inside an open folder") as caught:
        read_project_bytes(project, _target(project))

    assert caught.value.errno == errno.ENOTSUP


@pytest.mark.parametrize(
    "path",
    [
        Path("elsewhere") / "f.txt",
        Path("{root}") / "a" / ".." / ".." / "f.txt",
    ],
    ids=["outside", "dot-dot"],
)
def test_a_path_that_leaves_the_root_is_not_opened(project: Path, path: Path) -> None:
    built = Path(str(path).replace("{root}", str(project)))
    with pytest.raises(FileNotFoundError):
        read_project_bytes(project, built)


def test_the_root_itself_is_a_folder(project: Path) -> None:
    with pytest.raises(IsADirectoryError):
        read_project_bytes(project, project)


@_WINDOWS_ONLY
@pytest.mark.parametrize("name", ["f.txt.", "f.txt ", "f.txt:stream"])
def test_a_name_win32_would_rewrite_is_not_opened(project: Path, name: str) -> None:
    """A trailing dot or space, or a stream, names another entry on Windows."""
    with pytest.raises(FileNotFoundError):
        read_project_bytes(project, project / "a" / "b" / "c" / name)


@_WINDOWS_ONLY
def test_a_device_name_is_an_ordinary_missing_file(project: Path) -> None:
    """``CON`` inside a folder is a file name to ``NtCreateFile``, not a device."""
    with pytest.raises(FileNotFoundError):
        read_project_bytes(project, project / "a" / "CON")


@pytest.mark.parametrize(
    "data",
    [
        b"plain\n",
        b"crlf\r\nlines\r\n",
        b"cr\rlines\r",
        b"mixed\r\n\r\r\n\n",
        b"\xef\xbb\xbfbom\n",
        b"no newline",
        b"",
        "café \U0001f600\n".encode(),
    ],
)
def test_text_matches_read_text(tmp_path: Path, data: bytes) -> None:
    """The text equals ``Path.read_text(encoding="utf-8")``, line endings too."""
    target = tmp_path / "t.md"
    target.write_bytes(data)

    assert read_project_text(tmp_path, target) == target.read_text(encoding="utf-8")


def test_bytes_that_are_not_utf8_raise_like_read_text(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    target.write_bytes(b"\xff\xfe")
    with pytest.raises(UnicodeDecodeError):
        target.read_text(encoding="utf-8")
    with pytest.raises(UnicodeDecodeError):
        read_project_text(tmp_path, target)


def test_bytes_are_read_as_they_are(tmp_path: Path) -> None:
    """No line ending is changed and a Ctrl-Z ends nothing, as in a C runtime
    text-mode read on Windows."""
    data = b"a\r\nb\x1ac\rd\n"
    target = tmp_path / "raw.bin"
    target.write_bytes(data)

    assert read_project_bytes(tmp_path, target) == data


def test_max_bytes_caps_the_read(tmp_path: Path) -> None:
    target = tmp_path / "big.bin"
    target.write_bytes(b"x" * 100)

    assert read_project_bytes(tmp_path, target, max_bytes=11) == b"x" * 11


def test_a_name_in_another_letter_case_opens_as_the_host_does(project: Path) -> None:
    """Windows matches a name without letter case, as a Win32 open does."""
    upper = project / "A" / "B" / "C" / "F.TXT"
    if os.name == "nt":
        assert read_project_bytes(project, upper) == _INSIDE
    elif not upper.exists():
        with pytest.raises(FileNotFoundError):
            read_project_bytes(project, upper)


# ---------------------------------------------------------------------------
# Reparse points that are not links (Windows)
# ---------------------------------------------------------------------------


@_WINDOWS_ONLY
@pytest.mark.parametrize("depth", range(len(_LEVELS)))
@pytest.mark.parametrize(
    ("tag", "same_id", "outcome"),
    [
        (0x9000001A, True, "read"),  # a cloud sync placeholder, hydrated
        (0x80000013, True, "read"),  # Data Deduplication
        (None, True, "read"),  # a file system that gives no tag
        (0x9000001A, False, "refused"),  # the second open met another entry
        (0xA000000C, True, "refused"),  # a symbolic link
    ],
    ids=["cloud", "dedup", "no-tag", "other-entry", "symlink"],
)
def test_a_reparse_point_that_is_not_a_link_is_read_through_its_filter(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    depth: int,
    tag: int | None,
    same_id: bool,
    outcome: str,
) -> None:
    """At any level, a tag that is not a link is opened a second time without
    the reparse flag, and that second handle must name the same entry."""
    shown = _level(project, depth)
    real_tag, real_id = _safe_open._reparse_tag, _safe_open._file_id
    tagged: set[int] = set()
    real_create = _safe_open._create_relative
    options_seen: list[tuple[str, int]] = []

    def creating(parent: int, name: str, access: int, options: int, at: Path) -> int:
        handle = real_create(parent, name, access, options, at)
        options_seen.append((name, options & _safe_open.FILE_OPEN_REPARSE_POINT))
        if at == shown and options & _safe_open.FILE_OPEN_REPARSE_POINT:
            tagged.add(handle)
        return handle

    def reading_tag(handle: int) -> int | None:
        return tag if handle in tagged else real_tag(handle)

    def file_id(handle: int) -> tuple[int, int]:
        volume, index = real_id(handle)
        if not same_id and handle not in tagged and options_seen[-1][0] == "":
            return volume, index + 1
        return volume, index

    monkeypatch.setattr(_safe_open, "_create_relative", creating)
    monkeypatch.setattr(_safe_open, "_reparse_tag", reading_tag)
    monkeypatch.setattr(_safe_open, "_file_id", file_id)

    if outcome == "read":
        assert read_project_bytes(project, _target(project)) == _INSIDE
        flags = [flag for name, flag in options_seen if name == shown.name]
        assert flags == [_safe_open.FILE_OPEN_REPARSE_POINT]
        # The second open starts from the first handle, with no name.
        assert ("", 0) in options_seen
    else:
        with pytest.raises(ProjectFileRefusedError):
            read_project_bytes(project, _target(project))


def _final_path(handle: int) -> str:
    """Return the path Windows gives for the open *handle*."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    final = kernel32.GetFinalPathNameByHandleW
    final.argtypes = (
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
    )
    final.restype = ctypes.c_uint32
    buffer = ctypes.create_unicode_buffer(32768)
    if not final(handle, buffer, len(buffer), 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return buffer.value.removeprefix("\\\\?\\")


@_WINDOWS_ONLY
@pytest.mark.parametrize("depth", range(len(_LEVELS)))
def test_a_reparse_point_swapped_for_a_junction_between_opens_is_not_followed(
    project: Path, monkeypatch: pytest.MonkeyPatch, depth: int
) -> None:
    """A level whose tag is not a link is opened a second time. When its name
    is swapped for a junction out of the project between the two opens, the
    second open still reaches the file the first one opened, never the
    junction's target."""
    shown = _level(project, depth)
    outside = project.parent / "outside"
    tagged: set[int] = set()
    reached: list[str] = []
    real_create, real_tag = _safe_open._create_relative, _safe_open._reparse_tag

    def creating(parent: int, name: str, access: int, options: int, at: Path) -> int:
        handle = real_create(parent, name, access, options, at)
        reached.append(_final_path(handle))
        if at == shown and options & _safe_open.FILE_OPEN_REPARSE_POINT and not tagged:
            tagged.add(handle)
            shown.rename(shown.with_name(shown.name + ".moved"))
            target = _level(outside, depth)
            _link_folder(shown, target if depth < len(_LEVELS) - 1 else target.parent)
        return handle

    monkeypatch.setattr(_safe_open, "_create_relative", creating)
    monkeypatch.setattr(
        _safe_open,
        "_reparse_tag",
        lambda handle: 0x9000001A if handle in tagged else real_tag(handle),
    )

    try:
        data: bytes | None = read_project_bytes(project, _target(project))
    except ProjectFileRefusedError:
        data = None

    assert tagged, "the first open never reached the level"
    base = os.path.normcase(os.path.realpath(outside))
    assert [path for path in reached if os.path.normcase(path).startswith(base)] == []
    assert data in (None, _INSIDE)


@_WINDOWS_ONLY
def test_the_file_id_compared_is_the_128_bit_one(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two files whose IDs differ only above the low 64 bits (ReFS) differ."""

    def query(handle: int, info_class: int, info: ctypes.Structure) -> bool:
        assert info_class == _safe_open._FILE_ID_INFO
        info.volume = 7  # type: ignore[attr-defined]
        info.file_id[15] = handle  # type: ignore[attr-defined]
        return True

    monkeypatch.setattr(_safe_open, "_query", query)

    assert _safe_open._file_id(1) == (7, 1 << 120)
    assert _safe_open._file_id(1) != _safe_open._file_id(2)


@_WINDOWS_ONLY
def test_a_file_system_without_the_128_bit_id_gives_the_64_bit_index(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_safe_open, "_query", lambda handle, info_class, info: False)
    with open_project_file(project, _target(project)) as handle:
        import msvcrt

        volume, index = _safe_open._file_id(msvcrt.get_osfhandle(handle.fileno()))
        info = os.fstat(handle.fileno())

    assert index == info.st_ino & ((1 << 64) - 1)
    assert volume == info.st_dev & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Handles: no folder stays open
# ---------------------------------------------------------------------------


def _count_handles(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[int]]:
    """Record every folder or file level opened, and every handle closed here."""
    opened: list[str] = []
    closed: list[int] = []
    real_root, real_level, real_close = (
        _safe_open._open_root,
        _safe_open._open_level,
        _safe_open._close_handle,
    )

    def opening_root(root: Path) -> int:
        opened.append("<root>")
        return real_root(root)

    def opening_level(parent: int, name: str, *, folder: bool, shown: Path) -> int:
        opened.append(name)
        return real_level(parent, name, folder=folder, shown=shown)

    def closing(handle: int) -> None:
        closed.append(handle)
        real_close(handle)

    monkeypatch.setattr(_safe_open, "_open_root", opening_root)
    monkeypatch.setattr(_safe_open, "_open_level", opening_level)
    monkeypatch.setattr(_safe_open, "_close_handle", closing)
    return opened, closed


def test_without_a_skip_log_every_folder_is_closed(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A check called on its own keeps no folder open after a read."""
    opened, closed = _count_handles(monkeypatch)

    assert read_project_bytes(project, _target(project)) == _INSIDE
    assert read_project_bytes(project, _target(project)) == _INSIDE

    # The root and three folders, twice; the file closes with its file object.
    assert opened == ["<root>", "a", "b", "c", "f.txt"] * 2
    assert len(closed) == 8


def test_a_run_keeps_no_folder_open_between_reads(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """While a skip log runs too, each read opens its folders afresh and
    closes every one of them."""
    (project / "a" / "b" / "c" / "g.txt").write_bytes(b"g\n")
    opened, closed = _count_handles(monkeypatch)
    _project_paths.start_skip_log(project)

    read_project_bytes(project, _target(project))
    read_project_bytes(project, project / "a" / "b" / "c" / "g.txt")

    assert opened == [
        "<root>",
        "a",
        "b",
        "c",
        "f.txt",
        "<root>",
        "a",
        "b",
        "c",
        "g.txt",
    ]
    assert len(closed) == 8


def test_a_folder_swapped_for_a_link_after_a_read_is_refused_and_noted(
    project: Path,
) -> None:
    """A folder read once may be renamed afterwards, Windows too, and a link
    in its place is refused and noted at the next read."""
    _project_paths.start_skip_log(project)
    assert read_project_bytes(project, _target(project)) == _INSIDE
    (project / "a").rename(project / "a-moved")
    _link_folder(project / "a", project.parent / "outside" / "a")

    with pytest.raises(ProjectFileRefusedError):
        read_project_bytes(project, _target(project))

    assert _project_paths.take_skipped_paths() == ["a"]


def test_a_folder_recreated_after_a_read_is_read_afresh(project: Path) -> None:
    """A tool that deletes a folder and makes it again between two reads
    leaves the second read the new folder's file, not a missing one."""
    _project_paths.start_skip_log(project)
    assert read_project_bytes(project, _target(project)) == _INSIDE
    _remove_level(project / "a")
    _tree(project, b"again\n")

    assert read_project_bytes(project, _target(project)) == b"again\n"


def test_an_open_file_is_a_readable_binary_file(project: Path) -> None:
    with open_project_file(project, _target(project)) as handle:
        assert handle.read() == _INSIDE


# A project file each of five validators reads, which they once caught only
# as missing (REFUSED_OR_GONE): any other OSError would end the run with a
# traceback instead of a report.
_UNREADABLE_CASES = [
    pytest.param(
        cross_platform_matrix_grep.check,
        (".github/workflows/ci-matrix.yml",),
        id="cross-platform-matrix",
    ),
    pytest.param(
        oidc_trusted_publishing_grep.check,
        (".github/workflows/publish-pypi.yml", ".github/workflows/publish-npm.yml"),
        id="oidc-trusted-publishing",
    ),
    pytest.param(
        plans_discipline_language_grep.check,
        (
            plans_discipline_language_grep.FIXTURE_PATH,
            *plans_discipline_language_grep.REQUIRED_SURFACES,
        ),
        id="plans-discipline-language",
    ),
    pytest.param(
        smoke_install_grep.check,
        ("scripts/installer/install.sh", "scripts/installer/install.ps1"),
        id="smoke-install",
    ),
    pytest.param(
        workflow_concurrency_grep.check,
        (".github/workflows/ci.yml",),
        id="workflow-concurrency",
    ),
]


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(PermissionError(errno.EACCES, "access denied"), id="denied"),
        pytest.param(OSError(errno.ENOTSUP, "no openat here"), id="unsupported"),
    ],
)
@pytest.mark.parametrize(("check", "names"), _UNREADABLE_CASES)
def test_a_validator_reports_a_file_it_cannot_read_as_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    check: Callable[[Path], Any],
    names: tuple[str, ...],
    error: OSError,
) -> None:
    """A file that is there but cannot be read, for a reason other than a
    swap, fails the run with a finding that names it unreadable."""
    root = tmp_path / "project"
    for name in names:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("name: x\n", encoding="utf-8")

    def refuse(_root: Path, path: Path) -> bytes:
        raise type(error)(error.errno, error.strerror, str(path))

    monkeypatch.setattr(_safe_open, "read_project_bytes", refuse)

    result = check(root)

    assert result.passed is False
    details = [finding.detail for finding in result.findings]
    unreadable = [detail for detail in details if "unreadable" in detail]
    assert len(unreadable) == len(names), details
    assert all(str(error.strerror) in detail for detail in unreadable)
    json.loads(result.to_json())
