# SPDX-License-Identifier: MIT

"""The guarded open reads a project file one level at a time, never through a link.

Why these tests exist. Every ``--all`` validator and the ``--all-perwrite``
corpus run read project files through ``_safe_open``: the root is opened, then
each folder inside the folder opened before it, then the file, and no open
follows a link. These tests put each kind of entry (a real folder, a folder
link or junction, a file, a missing name, a named pipe, a file link) at each
level of a four-level path and check what the open does; they check that a
reparse point that is not a link (a cloud placeholder, a deduplicated file) is
read through its filter on Windows, that the text read matches
``Path.read_text``, and that the folder cache holds handles only during one
run and never more than its limit.
"""

from __future__ import annotations

import errno
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from apothem.conformity import _project_paths, _safe_open
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


@pytest.fixture(autouse=True)
def _no_skip_log() -> Iterator[None]:
    """Leave no skip log or open folder behind for the next test."""
    yield
    _project_paths.take_skipped_paths()
    _safe_open.clear_folder_cache()


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
    """A named pipe is not opened as a file, and never makes the read wait."""
    level = _level(project, depth)
    _remove_level(level)
    os.mkfifo(level)
    _project_paths.start_skip_log(project)

    expected = (
        ProjectFileRefusedError if depth == len(_LEVELS) - 1 else NotADirectoryError
    )
    with pytest.raises(expected):
        read_project_bytes(project, _target(project))

    noted = ["a/b/c/f.txt"] if expected is ProjectFileRefusedError else []
    assert _project_paths.take_skipped_paths() == noted


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
        if not same_id and handle not in tagged and options_seen[-1][0] == shown.name:
            return volume, index + 1
        return volume, index

    monkeypatch.setattr(_safe_open, "_create_relative", creating)
    monkeypatch.setattr(_safe_open, "_reparse_tag", reading_tag)
    monkeypatch.setattr(_safe_open, "_file_id", file_id)

    if outcome == "read":
        assert read_project_bytes(project, _target(project)) == _INSIDE
        flags = [flag for name, flag in options_seen if name == shown.name]
        assert flags == [_safe_open.FILE_OPEN_REPARSE_POINT, 0]
    else:
        with pytest.raises(ProjectFileRefusedError):
            read_project_bytes(project, _target(project))


# ---------------------------------------------------------------------------
# Handles and the folder cache
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
    assert len(_safe_open._cache) == 0


def test_a_run_reuses_open_folders_and_releases_them_at_its_end(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project / "a" / "b" / "c" / "g.txt").write_bytes(b"g\n")
    opened, closed = _count_handles(monkeypatch)
    _project_paths.start_skip_log(project)

    read_project_bytes(project, _target(project))
    read_project_bytes(project, project / "a" / "b" / "c" / "g.txt")

    assert opened == ["<root>", "a", "b", "c", "f.txt", "g.txt"]
    assert closed == []
    _project_paths.take_skipped_paths()
    assert len(closed) == 4
    assert len(_safe_open._cache) == 0


def test_the_cache_never_holds_more_than_its_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_safe_open, "FOLDER_CACHE_LIMIT", 3)
    for index in range(6):
        folder = tmp_path / f"d{index}" / "inner"
        folder.mkdir(parents=True)
        (folder / "f.txt").write_bytes(b"x")
    _project_paths.start_skip_log(tmp_path)

    for index in range(6):
        read_project_bytes(tmp_path, tmp_path / f"d{index}" / "inner" / "f.txt")
        assert len(_safe_open._cache) <= 3


def test_a_cached_folder_swapped_for_a_link_is_not_followed(project: Path) -> None:
    """The cache holds the folder that was opened, never a verdict on a name:
    a folder renamed and replaced by a link since is still the folder read.
    Windows does not let a folder with open folders below it be renamed at
    all while the run holds them."""
    _project_paths.start_skip_log(project)
    assert read_project_bytes(project, _target(project)) == _INSIDE
    if os.name == "nt":
        with pytest.raises(PermissionError):
            (project / "a").rename(project / "a-moved")
        return
    (project / "a").rename(project / "a-moved")
    _link_folder(project / "a", project.parent / "outside" / "a")

    data = read_project_bytes(project, _target(project))

    assert data == _INSIDE


def test_an_open_file_is_a_readable_binary_file(project: Path) -> None:
    with open_project_file(project, _target(project)) as handle:
        assert handle.read() == _INSIDE
