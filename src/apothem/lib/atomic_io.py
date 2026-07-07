# SPDX-License-Identifier: MIT

"""Shared atomic-write, durable-append, and advisory-lock filesystem utilities.

One implementation of each file-mutation primitive every state store and the
install driver share:

- :func:`write_bytes_atomically` — full-file replace through a sibling temp file
  + ``Path.replace`` (atomic; a crash leaves the original intact, never truncated).
- :func:`append_line_durably` — a single ``O_APPEND`` record with ``fsync`` of
  the fd and the parent directory, so an append-only ledger never rewrites the
  whole file (a torn full-file rewrite would lose every prior record; a torn
  append loses only the partial final record).
- :func:`advisory_lock` — one ratified cross-platform advisory file lock
  (``fcntl.flock`` on POSIX, ``msvcrt.locking`` on Windows) as a
  blocking-with-timeout context manager. Both release automatically on fd close
  or process death, so a killed holder leaves no orphan lock — NOT a bare
  ``O_EXCL`` marker file (which would deadlock on a crashed holder).
"""

from __future__ import annotations

import contextlib
import os
import stat
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Default ceiling for advisory-lock acquisition. A hung holder must not wedge
# every future acquirer forever; acquisition raises TimeoutError past this.
DEFAULT_LOCK_TIMEOUT = 30.0
_LOCK_POLL_INTERVAL = 0.05

# Bounded retry for the atomic replace on Windows, where antivirus scanners
# and concurrent readers briefly hold the target open and surface a transient
# PermissionError. POSIX rename never contends this way, so it gets 1 attempt.
_REPLACE_ATTEMPTS = 5
_REPLACE_RETRY_INTERVAL = 0.1


def write_bytes_atomically(path: Path, data: bytes) -> None:
    """Write *data* to *path* through a sibling temp file and an atomic replace.

    Creates parent directories, writes the bytes to a temp file in the target's
    own directory (so ``Path.replace`` is a same-filesystem rename), fsyncs the
    temp file, then replaces the target in one atomic operation. The temp file
    is cleaned up on any failure, so an interrupted write never leaves ``.tmp``
    residue and never yields a truncated target — the original is untouched
    until the single atomic replace.

    Permissions: a NEW file inherits ``tempfile.mkstemp``'s owner-only mode
    (0o600) — state written here is per-user and may carry profile-derived
    content, so it must not be created world-readable. When REPLACING an
    existing file, that file's prior permission bits are copied onto the temp
    file before the replace, so an operator-chosen mode (e.g. a 0o644 shared
    read) survives the rewrite. The copy is POSIX-effective; on Windows only
    the read-only bit is representable, which is harmless.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "wb") as tmp_file:
            tmp_file.write(data)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        # Preserve an existing target's permission bits across the replace;
        # an absent target keeps mkstemp's private 0o600 for the new file.
        with contextlib.suppress(FileNotFoundError):
            tmp_path.chmod(stat.S_IMODE(path.stat().st_mode))
        _replace_with_retry(tmp_path, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()


def _replace_with_retry(source: Path, target: Path) -> None:
    """Atomically replace *target* with *source*, retrying transient denials.

    On Windows a concurrent reader or an antivirus scan can hold the target
    open, making ``os.replace`` fail with a transient ``PermissionError``;
    retry up to ``_REPLACE_ATTEMPTS`` times with a short sleep and re-raise
    the final failure. POSIX rename does not contend this way — one attempt.

    os.replace (not Path.replace): pathlib on 3.10 binds os.replace at
    import time via its accessor, so a test monkeypatching os.replace
    cannot intercept Path.replace there. Calling os.replace directly is
    the same same-filesystem atomic rename and is interceptable on every
    supported interpreter.
    """
    attempts = _REPLACE_ATTEMPTS if sys.platform == "win32" else 1
    for attempt in range(1, attempts + 1):
        try:
            os.replace(source, target)  # noqa: PTH105 — see rationale above
            return
        except PermissionError:
            if attempt == attempts:
                raise
            time.sleep(_REPLACE_RETRY_INTERVAL)


def append_line_durably(path: Path, line: str) -> None:
    """Append one newline-terminated *line* to *path* durably.

    Opens with ``O_APPEND`` (so concurrent appenders never overwrite each
    other's offset), writes exactly one record, then fsyncs the fd and the
    parent directory so the record survives a crash. Distinct from
    :func:`write_bytes_atomically`: this never rewrites the whole file, so a
    crash mid-append loses at most the partial final record — every prior
    record stays readable.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    record = line if line.endswith("\n") else f"{line}\n"
    # Owner-only (0o600): append records are per-user state and may carry
    # profile-derived content; a new file must not be created world-readable.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, record.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(path.parent)


def _fsync_dir(directory: Path) -> None:
    """Best-effort fsync of *directory* so a new/renamed entry is durable.

    Directory fsync is unsupported on some platforms (notably Windows), where
    the entry-durability guarantee is provided by the filesystem differently;
    failures are suppressed rather than propagated.
    """
    with contextlib.suppress(OSError, PermissionError):
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


@contextmanager
def advisory_lock(
    path: Path,
    *,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
    poll_interval: float = _LOCK_POLL_INTERVAL,
) -> Iterator[None]:
    """Hold an exclusive advisory OS lock on *path* for the block's duration.

    The one ratified primitive: a held-open lock file locked via
    ``fcntl.flock`` (POSIX) / ``msvcrt.locking`` (Windows). The lock releases
    on block exit (including on exception) and on process death / fd close, so
    a killed holder never orphans the lock. Acquisition retries until *timeout*
    seconds elapse, then raises :class:`TimeoutError` rather than blocking
    forever on a hung holder.

    Wrap read-modify-write windows (store updates, the operator-owned JSON/YAML
    merge, per-(harness, root) install passes) in this to serialize concurrent
    writers.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Owner-only (0o600): the lock file is per-user coordination state; a new
    # file must not be created world-readable.
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            if _try_acquire(fd):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"could not acquire advisory lock on {path} within {timeout}s"
                )
            time.sleep(poll_interval)
        try:
            yield
        finally:
            _release(fd)
    finally:
        os.close(fd)


def _try_acquire(fd: int) -> bool:
    """Attempt a non-blocking exclusive lock on *fd*; return success.

    Platform-guarded local imports keep both the Windows (``msvcrt``) and POSIX
    (``fcntl``) paths type-checkable on either platform — the unreachable branch
    is skipped under ``sys.platform`` narrowing.
    """
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _release(fd: int) -> None:
    """Release the lock held on *fd* (suppressing teardown races)."""
    with contextlib.suppress(OSError):
        if sys.platform == "win32":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)


__all__ = [
    "DEFAULT_LOCK_TIMEOUT",
    "advisory_lock",
    "append_line_durably",
    "write_bytes_atomically",
]
