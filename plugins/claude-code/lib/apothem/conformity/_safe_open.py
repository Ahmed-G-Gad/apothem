# SPDX-License-Identifier: MIT

"""Open a project file one level at a time, never through a link.

Why this module exists. A validator looks at a path with ``os.lstat`` or a
directory entry, then reads it. A program that writes to the project while the
gate runs can swap the file, or a folder above it, for a link or a named pipe
in between, and a read by name would then follow the link out of the project
or wait on the pipe until the gate's time limit. So the read does not go by
name: :func:`open_project_file` opens the root, then each folder below it
inside the folder already open, and the file last, and none of those opens
follows a link.

- POSIX: each level is looked at with ``fstatat`` and opened with ``openat``
  and ``O_NOFOLLOW`` inside the folder opened just before it (folders with
  ``O_DIRECTORY``, the file with ``O_NONBLOCK`` so a named pipe cannot make
  the open wait). The opened level must be the one looked at (same device and
  inode, same type), and the file must be a regular file; the file is then
  set back to blocking reads.
- Windows: each level is opened with ``NtCreateFile`` inside the folder handle
  opened just before it, with ``FILE_OPEN_REPARSE_POINT``, so a reparse point
  is opened itself. One whose tag names another file or folder (a symbolic
  link, a junction) is refused. Any other reparse point, such as a cloud
  placeholder or a deduplicated file, is opened once more without the flag so
  its filter gives the real content, and the second handle must name the same
  file. Names are taken as written: Win32 does not rewrite a trailing dot, and
  ``CON`` is a file name there, not a device.

A refusal raises :class:`ProjectFileRefusedError` (``ELOOP``) and notes the level
that was refused in the skip log, so the report lists it under
``skipped_links``. While a skip log runs (one command-line run of a
validator), the folders opened stay open in a small cache, so the next file in
the same folder costs one open; the cache holds handles, never verdicts, and
is released when the log stops.

What it does not cover. A hard link reads as an ordinary file, and a file
system that gives no inode or file ID cannot show a swap to another regular
file (see the conformity README).
"""

from __future__ import annotations

import errno
import os
import stat
import sys
import threading
from collections import OrderedDict
from pathlib import Path
from typing import BinaryIO, Final, NoReturn

from apothem.conformity._project_paths import (
    NAME_SURROGATE_TAG_BIT,
    note_skipped,
    on_skip_log_bounds,
    skip_log_running,
)

# How many folders one run keeps open at most: enough for the folders a
# validator reads in turn, few enough to leave the process its file handles.
FOLDER_CACHE_LIMIT: Final[int] = 64


class ProjectFileRefusedError(OSError):
    """A level of the path was a link, a special file, or changed while opened.

    Its ``errno`` is ``ELOOP``, as an ``O_NOFOLLOW`` open reports a link, and
    it is an ``OSError``, so a caller that skips an unreadable file skips this
    one too. The refused level is already noted in the skip log.
    """


# The errors that say the entry a caller checked is no longer the regular file
# it found: a link or special file took its place (noted in the skip log), or
# it, or a folder above it, is gone or changed kind. A caller that treats a
# link as a missing file treats these the same way.
REFUSED_OR_GONE: Final[tuple[type[OSError], ...]] = (
    ProjectFileRefusedError,
    FileNotFoundError,
    NotADirectoryError,
    IsADirectoryError,
)


def _refuse(shown: Path, why: str) -> NoReturn:
    """Note *shown* in the skip log and raise :class:`ProjectFileRefusedError`."""
    note_skipped(shown)
    raise ProjectFileRefusedError(errno.ELOOP, why, str(shown))


def _missing(path: Path, why: str) -> FileNotFoundError:
    return FileNotFoundError(errno.ENOENT, why, str(path))


def _parts_inside(root: Path, path: Path) -> tuple[str, ...]:
    """Return the names of *path* below *root*, or raise as for a missing file.

    *path* was built from *root*. A path outside it, with a ``..`` part or a
    NUL, or on Windows with a part Win32 would rewrite (a trailing dot or
    space) or a colon (a stream), is not opened; the root itself is a folder.
    """
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        raise _missing(path, "the path is not inside the project") from None
    if not parts:
        raise IsADirectoryError(errno.EISDIR, "the project root is a folder", str(path))
    for part in parts:
        if part in ("", ".", "..") or "\0" in part:
            raise _missing(path, "the path leaves the project")
        if os.name == "nt" and (part.endswith((".", " ")) or ":" in part):
            raise _missing(path, "Windows would open another name")
    return parts


# ---------------------------------------------------------------------------
# The folder cache
# ---------------------------------------------------------------------------

_cache: OrderedDict[tuple[str, tuple[str, ...]], int] = OrderedDict()
# One open at a time: a handle the cache closes is never in use elsewhere.
_lock = threading.RLock()


def clear_folder_cache() -> None:
    """Close every folder the cache holds."""
    with _lock:
        while _cache:
            _, handle = _cache.popitem(last=False)
            _close_handle(handle)


on_skip_log_bounds(clear_folder_cache)


def _trim_cache() -> None:
    while len(_cache) > FOLDER_CACHE_LIMIT:
        _, handle = _cache.popitem(last=False)
        _close_handle(handle)


def _folder_handle(root: Path, folders: tuple[str, ...], transient: list[int]) -> int:
    """Return a handle to ``root/<folders>``, opened level by level.

    While a skip log runs, the deepest folder already open is taken from the
    cache and every folder opened is kept there; otherwise each one is added to
    *transient* for the caller to close.
    """
    caching = skip_log_running()
    key = os.fspath(root)
    handle: int | None = None
    depth = len(folders)
    if caching:
        while depth >= 0:
            cached = _cache.get((key, folders[:depth]))
            if cached is not None:
                _cache.move_to_end((key, folders[:depth]))
                handle = cached
                break
            depth -= 1
    if handle is None:
        depth = 0
        handle = _open_root(root)
        _keep(handle, (key, ()), caching, transient)
    for level in range(depth, len(folders)):
        shown = root.joinpath(*folders[: level + 1])
        handle = _open_level(handle, folders[level], folder=True, shown=shown)
        _keep(handle, (key, folders[: level + 1]), caching, transient)
    return handle


def _keep(
    handle: int,
    key: tuple[str, tuple[str, ...]],
    caching: bool,
    transient: list[int],
) -> None:
    if caching:
        _cache[key] = handle
    else:
        transient.append(handle)


# ---------------------------------------------------------------------------
# The public reads
# ---------------------------------------------------------------------------


def open_project_file(root: Path, path: Path) -> BinaryIO:
    """Open the regular file *path* below *root* to read bytes.

    Pre-conditions: *path* was built from *root*, with the same spelling; the
    caller trusts *root* itself. Post-conditions: the file returned was reached
    through real folders inside *root* and is a regular file. A link, a
    junction or a special file at any level, or a level swapped while it was
    opened, raises :class:`ProjectFileRefusedError` and is noted in the skip log; a
    missing level raises ``FileNotFoundError``, a file on the way
    ``NotADirectoryError``, and a folder in the file's place
    ``IsADirectoryError``. Nothing outside *root* is opened.
    """
    parts = _parts_inside(root, path)
    with _lock:
        transient: list[int] = []
        try:
            parent = _folder_handle(root, parts[:-1], transient)
            handle = _open_level(parent, parts[-1], folder=False, shown=path)
        finally:
            for folder in reversed(transient):
                _close_handle(folder)
            _trim_cache()
    return _as_binary_file(handle, path)


def read_project_bytes(root: Path, path: Path, max_bytes: int | None = None) -> bytes:
    """Return the bytes of *path* (see :func:`open_project_file`).

    With *max_bytes*, at most that many leading bytes are read.
    """
    with open_project_file(root, path) as handle:
        return handle.read() if max_bytes is None else handle.read(max_bytes)


def read_project_text(root: Path, path: Path) -> str:
    """Return *path* as UTF-8 text, as ``Path.read_text(encoding="utf-8")`` would.

    Bytes that are not UTF-8 raise ``UnicodeDecodeError``, and line endings
    become ``\\n``, as with the universal newlines ``read_text`` uses.
    """
    text = read_project_bytes(root, path).decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ---------------------------------------------------------------------------
# POSIX
# ---------------------------------------------------------------------------

if sys.platform != "win32":
    # The errors an O_NOFOLLOW open gives for a link at the last level: ELOOP,
    # EMLINK on FreeBSD, EFTYPE on NetBSD.
    _LINK_ERRNOS: Final[frozenset[int]] = frozenset(
        code
        for code in (
            errno.ELOOP,
            errno.EMLINK,
            getattr(errno, "EFTYPE", errno.ELOOP),
        )
    )

    def _same_entry(seen: os.stat_result, opened: os.stat_result) -> bool:
        """Return True when *opened* is the entry *seen* named (0 is no inode)."""
        if not seen.st_ino or not opened.st_ino:
            return True
        return (seen.st_dev, seen.st_ino) == (opened.st_dev, opened.st_ino)

    def _open_root(root: Path) -> int:
        """Open the folder *root*, which the caller trusts, as given."""
        return os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)

    def _open_level(parent: int, name: str, *, folder: bool, shown: Path) -> int:
        """Open *name* inside the open folder *parent* without following it.

        *folder* says whether a folder or a regular file is wanted; *shown*
        is the full path, for errors and the skip log.
        """
        try:
            seen = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except OSError as exc:
            exc.filename = str(shown)
            raise
        if stat.S_ISLNK(seen.st_mode):
            _refuse(shown, "a link is in the way")
        if folder:
            if not stat.S_ISDIR(seen.st_mode):
                raise NotADirectoryError(errno.ENOTDIR, "not a folder", str(shown))
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            wanted = stat.S_ISDIR
        else:
            if stat.S_ISDIR(seen.st_mode):
                raise IsADirectoryError(errno.EISDIR, "a folder", str(shown))
            if not stat.S_ISREG(seen.st_mode):
                _refuse(shown, "not a regular file")
            flags = (
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC
            )
            wanted = stat.S_ISREG
        try:
            fd = os.open(name, flags, dir_fd=parent)
        except OSError as exc:
            if exc.errno in _LINK_ERRNOS or (folder and exc.errno == errno.ENOTDIR):
                _refuse(shown, "the entry changed since it was looked at")
            exc.filename = str(shown)
            raise
        try:
            opened = os.fstat(fd)
            if not wanted(opened.st_mode) or not _same_entry(seen, opened):
                _refuse(shown, "the entry changed since it was looked at")
            if not folder:
                os.set_blocking(fd, True)
        except BaseException:
            os.close(fd)
            raise
        return fd

    def _close_handle(handle: int) -> None:
        os.close(handle)

    def _as_binary_file(handle: int, path: Path) -> BinaryIO:
        """Wrap the open file descriptor *handle* as a binary file object."""
        try:
            return os.fdopen(handle, "rb")
        except BaseException:
            os.close(handle)
            raise


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    import functools
    import msvcrt
    from ctypes import wintypes

    # Access rights: a folder is only a place to open names in; a file is read.
    _SYNCHRONIZE: Final[int] = 0x00100000
    _FILE_READ_ATTRIBUTES: Final[int] = 0x0080
    _GENERIC_READ: Final[int] = 0x80000000
    _FOLDER_ACCESS: Final[int] = _FILE_READ_ATTRIBUTES | _SYNCHRONIZE
    _FILE_ACCESS: Final[int] = _GENERIC_READ | _SYNCHRONIZE
    # Share read, write and delete, so the gate's open conflicts only with a
    # holder that does not share reading.
    _SHARE_ALL: Final[int] = 0x7
    # NtCreateFile: open an existing entry only.
    _FILE_OPEN: Final[int] = 1
    # NtCreateFile options: the entry must be a folder; reads and writes wait
    # (the C runtime needs that); a reparse point is opened itself.
    _FILE_DIRECTORY_FILE: Final[int] = 0x00000001
    _FILE_SYNCHRONOUS_IO_NONALERT: Final[int] = 0x00000020
    FILE_OPEN_REPARSE_POINT: Final[int] = 0x00200000
    # Names match without letter case, as a Win32 open does; a folder marked
    # case-sensitive keeps its own rule.
    _OBJ_CASE_INSENSITIVE: Final[int] = 0x00000040
    # A server behind a name may only identify the gate, never act as it.
    _SECURITY_IDENTIFICATION_LEVEL: Final[int] = 1
    _SECURITY_STATIC_TRACKING: Final[int] = 0
    # CreateFileW for the root: open a folder, and the same identification
    # limit (SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION).
    _FILE_FLAG_BACKUP_SEMANTICS: Final[int] = 0x02000000
    _SECURITY_SQOS_IDENTIFICATION: Final[int] = 0x00100000 | 0x00010000
    _OPEN_EXISTING: Final[int] = 3
    # The FILE_INFO_BY_HANDLE_CLASS value of a file's attributes and reparse tag.
    _FILE_ATTRIBUTE_TAG_INFO: Final[int] = 9
    # The Windows errors a file system gives for an information class it does
    # not have: invalid function, not supported, invalid parameter.
    _QUERY_NOT_SUPPORTED: Final[frozenset[int]] = frozenset({1, 50, 87})
    _INVALID_HANDLE: Final[int | None] = ctypes.c_void_p(-1).value

    class _UnicodeString(ctypes.Structure):
        """``UNICODE_STRING``: a counted UTF-16 name."""

        _fields_ = (
            ("length", ctypes.c_ushort),
            ("maximum_length", ctypes.c_ushort),
            ("buffer", ctypes.c_wchar_p),
        )

    class _SecurityQualityOfService(ctypes.Structure):
        """``SECURITY_QUALITY_OF_SERVICE``."""

        _fields_ = (
            ("length", wintypes.DWORD),
            ("impersonation_level", ctypes.c_int),
            ("context_tracking_mode", ctypes.c_ubyte),
            ("effective_only", ctypes.c_ubyte),
        )

    class _ObjectAttributes(ctypes.Structure):
        """``OBJECT_ATTRIBUTES``: a name relative to an open folder."""

        _fields_ = (
            ("length", wintypes.ULONG),
            ("root_directory", wintypes.HANDLE),
            ("object_name", ctypes.POINTER(_UnicodeString)),
            ("attributes", wintypes.ULONG),
            ("security_descriptor", ctypes.c_void_p),
            ("security_quality_of_service", ctypes.c_void_p),
        )

    class _IoStatusBlock(ctypes.Structure):
        """``IO_STATUS_BLOCK``."""

        _fields_ = (("status", ctypes.c_void_p), ("information", ctypes.c_size_t))

    class _AttributeTagInfo(ctypes.Structure):
        """``FILE_ATTRIBUTE_TAG_INFO``: a file's attributes and reparse tag."""

        _fields_ = (("attributes", wintypes.DWORD), ("tag", wintypes.DWORD))

    class _ByHandleFileInformation(ctypes.Structure):
        """``BY_HANDLE_FILE_INFORMATION``, of which the file ID is used."""

        _fields_ = tuple(
            (name, wintypes.DWORD)
            for name in (
                "attributes",
                "created_low",
                "created_high",
                "accessed_low",
                "accessed_high",
                "written_low",
                "written_high",
                "volume_serial",
                "size_high",
                "size_low",
                "links",
                "index_high",
                "index_low",
            )
        )

    @functools.cache
    def _kernel32() -> ctypes.WinDLL:
        """Return ``kernel32`` with the calls used here typed, built once."""
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        by_class = kernel32.GetFileInformationByHandleEx
        by_class.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        by_class.restype = wintypes.BOOL
        basic = kernel32.GetFileInformationByHandle
        basic.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
        basic.restype = wintypes.BOOL
        create = kernel32.CreateFileW
        create.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        create.restype = wintypes.HANDLE
        close = kernel32.CloseHandle
        close.argtypes = (wintypes.HANDLE,)
        close.restype = wintypes.BOOL
        return kernel32

    @functools.cache
    def _ntdll() -> ctypes.WinDLL:
        """Return ``ntdll`` with ``NtCreateFile`` and its error mapping typed."""
        ntdll = ctypes.WinDLL("ntdll")
        create = ntdll.NtCreateFile
        create.argtypes = (
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.ULONG,
            ctypes.POINTER(_ObjectAttributes),
            ctypes.POINTER(_IoStatusBlock),
            ctypes.c_void_p,
            wintypes.ULONG,
            wintypes.ULONG,
            wintypes.ULONG,
            wintypes.ULONG,
            ctypes.c_void_p,
            wintypes.ULONG,
        )
        create.restype = ctypes.c_long
        to_dos = ntdll.RtlNtStatusToDosError
        to_dos.argtypes = (wintypes.ULONG,)
        to_dos.restype = wintypes.ULONG
        return ntdll

    def _windows_error(code: int, shown: Path) -> OSError:
        """Return the ``OSError`` for the Windows error *code* at *shown*."""
        exc = ctypes.WinError(code)
        exc.filename = str(shown)
        return exc

    def _open_root(root: Path) -> int:
        """Open the folder *root*, which the caller trusts, as given."""
        handle = _kernel32().CreateFileW(
            str(root),
            _FOLDER_ACCESS,
            _SHARE_ALL,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS | _SECURITY_SQOS_IDENTIFICATION,
            None,
        )
        if handle is None or handle == _INVALID_HANDLE:
            raise _windows_error(ctypes.get_last_error(), root)
        return int(handle)

    def _create_relative(
        parent: int, name: str, access: int, options: int, shown: Path
    ) -> int:
        """Open *name* inside the open folder *parent* with ``NtCreateFile``."""
        size = len(name.encode("utf-16-le"))
        text = _UnicodeString(size, size, name)
        quality = _SecurityQualityOfService(
            ctypes.sizeof(_SecurityQualityOfService),
            _SECURITY_IDENTIFICATION_LEVEL,
            _SECURITY_STATIC_TRACKING,
            0,
        )
        attributes = _ObjectAttributes(
            ctypes.sizeof(_ObjectAttributes),
            parent,
            ctypes.pointer(text),
            _OBJ_CASE_INSENSITIVE,
            None,
            ctypes.cast(ctypes.pointer(quality), ctypes.c_void_p),
        )
        status_block = _IoStatusBlock()
        handle = wintypes.HANDLE()
        status = _ntdll().NtCreateFile(
            ctypes.byref(handle),
            access,
            ctypes.byref(attributes),
            ctypes.byref(status_block),
            None,
            0,
            _SHARE_ALL,
            _FILE_OPEN,
            options,
            None,
            0,
        )
        if status < 0:
            code = _ntdll().RtlNtStatusToDosError(status & 0xFFFFFFFF)
            raise _windows_error(code, shown)
        if handle.value is None:  # pragma: no cover - a success gives a handle
            raise _windows_error(6, shown)  # ERROR_INVALID_HANDLE
        return int(handle.value)

    def _close_handle(handle: int) -> None:
        _kernel32().CloseHandle(handle)

    def _reparse_tag(handle: int) -> int | None:
        """Return the reparse tag of the open file *handle*: 0 for none, or None
        when the file system does not give one.

        ``os.fstat`` reports no tag on Windows, so the attribute and tag record
        (``FileAttributeTagInfo``) is read from the handle. Any other failure
        raises ``OSError``, so the entry is not used.
        """
        info = _AttributeTagInfo()
        query = _kernel32().GetFileInformationByHandleEx
        if not query(
            handle, _FILE_ATTRIBUTE_TAG_INFO, ctypes.byref(info), ctypes.sizeof(info)
        ):
            error = ctypes.get_last_error()
            if error in _QUERY_NOT_SUPPORTED:
                return None
            raise ctypes.WinError(error)
        if not info.attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            return 0
        return int(info.tag)

    def _file_id(handle: int) -> tuple[int, int]:
        """Return the volume and file index of the open file *handle*."""
        info = _ByHandleFileInformation()
        if not _kernel32().GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.volume_serial, (info.index_high << 32) | info.index_low

    def _open_level(parent: int, name: str, *, folder: bool, shown: Path) -> int:
        """Open *name* inside the open folder *parent* without following it.

        The first open takes the reparse point itself. A tag that names
        another file or folder is refused; a plain entry is used through that
        handle. Any other reparse point, or an entry whose file system gives no
        tag, is opened again without the flag, so its filter gives the real
        content, and the second handle must name the same entry; when no
        filter claims the tag (its program is stopped), that open fails and
        the entry is unreadable rather than read as its empty stub.
        """
        access = _FOLDER_ACCESS if folder else _FILE_ACCESS
        options = _FILE_SYNCHRONOUS_IO_NONALERT
        if folder:
            options |= _FILE_DIRECTORY_FILE
        first = _create_relative(
            parent, name, access, options | FILE_OPEN_REPARSE_POINT, shown
        )
        try:
            tag = _reparse_tag(first)
            if tag is not None and tag & NAME_SURROGATE_TAG_BIT:
                _refuse(shown, "a link is in the way")
            if tag == 0:
                return first
            second = _create_relative(parent, name, access, options, shown)
            try:
                if _file_id(second) != _file_id(first):
                    _refuse(shown, "the entry changed between opens")
            except BaseException:
                _close_handle(second)
                raise
        except BaseException:
            _close_handle(first)
            raise
        _close_handle(first)
        return second

    def _as_binary_file(handle: int, path: Path) -> BinaryIO:
        """Wrap the open file *handle* as a binary file object; it must be a
        regular file (``NtCreateFile`` also opens a folder by that name)."""
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
        except BaseException:
            _close_handle(handle)
            raise
        try:
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise IsADirectoryError(errno.EISDIR, "a folder", str(path))
            return os.fdopen(fd, "rb")
        except BaseException:
            os.close(fd)
            raise
