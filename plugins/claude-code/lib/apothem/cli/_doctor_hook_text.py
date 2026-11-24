# SPDX-License-Identifier: MIT

"""Read hook files and spell paths for ``doctor``'s hook probe.

The helpers here look at text and parsed JSON only, apart from :func:`walk`
and :func:`sha256_of`, which list and read a hook folder the probe already
trusts, and :func:`read_hook_file`, which reads one hook file. None of them
starts a program. :mod:`apothem.cli._doctor_hooks` uses them to find the hook
commands an install registered and to judge them, and keeps what it finds in
:class:`RegisteredHooks`.
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import BinaryIO, Final

from apothem.harnesses._shared.install_driver import is_apothem_hook
from apothem.lib.links import is_link

#: Marks the end of one level of :func:`user_handlers`'s walk.
_DONE = object()

#: The largest hook file doctor reads, and the largest hook script it hashes,
#: in bytes; every one Apothem writes is far smaller. A project's committers
#: choose their size.
MAX_HOOK_FILE_BYTES: Final = 4 * 1024 * 1024

#: Bytes :func:`sha256_of` reads at a time.
_BLOCK_BYTES: Final = 1024 * 1024

#: How :func:`_open_regular` opens a file: read only, and, where the system has
#: the flag, without waiting for a writer on a pipe.
_OPEN_FLAGS: Final = (
    os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
)

#: Added to :data:`_OPEN_FLAGS` where a link must not be followed: the open
#: then fails on a link. Windows has no such flag.
_NO_FOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)

#: The errors an open refused by :data:`_NO_FOLLOW` raises: ``ELOOP``, or
#: ``EMLINK`` on FreeBSD.
_LINK_ERRNOS: Final = frozenset({errno.ELOOP, errno.EMLINK})

#: Whether the opened file must have the ``st_dev`` and ``st_ino`` the path had
#: when looked at. Off on Windows, where some Python releases report the file
#: ID of a path and of an open file in different widths.
_SAME_FILE_CHECK: Final = os.name != "nt"


@dataclass(frozen=True)
class HookProbe:
    """The outcome of starting one registered hook command."""

    command: str
    ok: bool
    detail: str


@dataclass
class RegisteredHooks:
    """The hook commands an install registered, as doctor reads them.

    *argvs* are the commands doctor may start, without repeats. *unstartable*
    holds the commands that cannot start because their interpreter or script
    does not exist; doctor reports them without starting anything.
    *unchecked* holds one sentence for each command or hook file doctor does
    not start, naming it and the reason. *run_with* maps each sentence whose
    fix needs a Python outside the project to the one the install recorded
    inside it, as data only: the fix never names it. Every sentence and
    command text has its control characters spelled out (:func:`printable`).
    """

    argvs: list[list[str]] = field(default_factory=list)
    unstartable: list[HookProbe] = field(default_factory=list)
    unchecked: list[str] = field(default_factory=list)
    run_with: dict[str, str] = field(default_factory=dict)
    # What each list already holds, so nothing is kept twice. One set per list:
    # an argv never stands in for a sentence, nor a sentence for an argv.
    _argvs_seen: set[tuple[str, ...]] = field(
        default_factory=set, init=False, repr=False, compare=False
    )
    _probes_seen: set[HookProbe] = field(
        default_factory=set, init=False, repr=False, compare=False
    )
    _notes_seen: set[str] = field(
        default_factory=set, init=False, repr=False, compare=False
    )

    def add(self, argv: list[str]) -> None:
        """Keep *argv* to start, unless an earlier handler registered it."""
        key = tuple(argv)
        if key not in self._argvs_seen:
            self._argvs_seen.add(key)
            self.argvs.append(argv)

    def cannot_start(self, probe: HookProbe) -> None:
        """Keep *probe* as a command that cannot start, once."""
        shown = HookProbe(printable(probe.command), probe.ok, printable(probe.detail))
        if shown not in self._probes_seen:
            self._probes_seen.add(shown)
            self.unstartable.append(shown)

    def note(self, reason: str, *, run_with: str | None = None) -> None:
        """Keep *reason* for a command or file doctor does not start, once."""
        shown = printable(reason)
        if shown in self._notes_seen:
            return
        self._notes_seen.add(shown)
        self.unchecked.append(shown)
        if run_with is not None:
            self.run_with[shown] = run_with


def spelling(path: str) -> str | None:
    """Return the comparable spelling of an absolute *path*, or ``None``.

    Purely lexical: case and separators are folded the way this system folds
    them, and nothing is looked up. A relative path, or one with a ``..``
    step, has no spelling: what it names depends on the links it passes.
    """
    pure = PurePath(path)
    if not pure.is_absolute() or ".." in pure.parts:
        return None
    return os.path.normcase(str(pure))


def resolved_spelling(root: Path) -> str | None:
    """Return the spelling of the project root as the system resolves it."""
    try:
        return spelling(str(root.resolve()))
    except (OSError, RuntimeError):
        return None


def printable(text: str) -> str:
    """Return *text* with each character a terminal would act on spelled out.

    Hook-line text, and the names in a project's hook folder, are the
    project's, not Apothem's: shown as they are, a control character in them
    could move the cursor or repaint the report.
    """
    return "".join(
        char if char.isprintable() else f"<{ord(char):#04x}>" for char in text
    )


def sha256_of(path: Path) -> str | None:
    """Return the SHA-256 of *path*'s bytes, or ``None`` when it cannot be read.

    The file is read a block at a time, so a large one costs no more memory.
    Anything but a regular file (:func:`_open_regular`), and a file larger than
    :data:`MAX_HOOK_FILE_BYTES`, cannot be read: no hook script Apothem writes
    is that large, so such a file has changed.
    """
    digest = hashlib.sha256()
    read = 0
    try:
        with _open_regular(path) as handle:
            if os.fstat(handle.fileno()).st_size > MAX_HOOK_FILE_BYTES:
                return None
            for block in iter(lambda: handle.read(_BLOCK_BYTES), b""):
                read += len(block)
                if read > MAX_HOOK_FILE_BYTES:  # it grew once open
                    return None
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


class HookFileTooLargeError(ValueError):
    """A hook file is larger than doctor reads (:data:`MAX_HOOK_FILE_BYTES`)."""


class NotARegularFileError(OSError):
    """A path doctor reads names a pipe, a device, a folder or a link, not a file."""


def _look(path: Path, *, follow_link: bool) -> os.stat_result:
    """Return *path*'s stat, following a link only with *follow_link*."""
    # One os module for every look, the seam the tests replace.
    return os.stat(path) if follow_link else os.lstat(path)  # noqa: PTH116


def _still_regular(path: Path, follow_link: bool) -> bool:
    """Return False when a second look finds *path* is no longer a regular file.

    A path that cannot be looked at again counts as still regular, so the
    open's own error is the one reported.
    """
    try:
        return stat.S_ISREG(_look(path, follow_link=follow_link).st_mode)
    except OSError:
        return True


def _open_regular(path: Path, *, follow_link: bool = False) -> BinaryIO:
    """Open *path* to read, only when it is a regular file and still one once open.

    The path is looked at first, so a pipe is never opened and the open cannot
    wait for a writer. Without *follow_link*, a link is not a regular file:
    the look does not follow it, and on POSIX neither does the open itself.
    With it, a link to a regular file is read, as for a file under the
    operator's own home, which a dotfile manager may keep as a link. Where the
    system has the flag, the open waits on no pipe, and on POSIX the opened
    file must be the one looked at (``st_dev`` and ``st_ino``), so a path
    swapped for a link or a device in between is not read. On Windows only the
    look before the open guards against such a swap: the system has no flag
    that refuses a link, and Python reports the file ID of a path and of an
    open file in different widths on some releases and file systems. An open
    that fails is looked at again, so a file swapped for a folder or a
    junction in between is named as not a regular file, not left unexplained.

    Raises:
        NotARegularFileError: *path* is not a regular file, before or once open.
        OSError: *path* cannot be looked up or opened.
    """
    before = _look(path, follow_link=follow_link)
    if not stat.S_ISREG(before.st_mode):
        raise NotARegularFileError(errno.EINVAL, "not a regular file", str(path))
    try:
        descriptor = os.open(path, _OPEN_FLAGS | (0 if follow_link else _NO_FOLLOW))
    except OSError as exc:
        # Swapped for a link since the look, or, on Windows, for a folder or a
        # junction, which the open refuses as access denied.
        if exc.errno in _LINK_ERRNOS or not _still_regular(path, follow_link):
            raise NotARegularFileError(
                errno.EINVAL, "not a regular file", str(path)
            ) from exc
        raise
    try:
        after = os.fstat(descriptor)
        if not stat.S_ISREG(after.st_mode) or (
            _SAME_FILE_CHECK and not os.path.samestat(before, after)
        ):
            raise NotARegularFileError(errno.EINVAL, "not a regular file", str(path))
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def read_hook_file(path: Path, *, follow_link: bool = False) -> str:
    """Return *path*'s text, reading no more than :data:`MAX_HOOK_FILE_BYTES`.

    *follow_link* reads a file reached through a link (:func:`_open_regular`).
    Raises :class:`HookFileTooLargeError` for a larger file,
    :class:`NotARegularFileError` for anything but a regular file,
    :class:`OSError` when it cannot be read, and :class:`UnicodeDecodeError`
    when it is not UTF-8.
    """
    with _open_regular(path, follow_link=follow_link) as handle:
        data = handle.read(MAX_HOOK_FILE_BYTES + 1)
    if len(data) > MAX_HOOK_FILE_BYTES:
        raise HookFileTooLargeError(path)
    return data.decode("utf-8")


def unread_reason(path: Path, error: Exception) -> str | None:
    """Return the note for a hook file *error* kept doctor from reading, or ``None``.

    A file too large to read, or one that is not a regular file, is always
    named: whatever else it holds, a tool may run hooks from it. Any other
    error gets ``None``, for the caller to judge.
    """
    if isinstance(error, HookFileTooLargeError):
        what = f"larger than {MAX_HOOK_FILE_BYTES // 2**20} MB"
    elif isinstance(error, NotARegularFileError):
        what = "not a regular file"
    else:
        return None
    return f"{path} is {what}, so no hook in it was read"


def unquoted(token: str) -> str:
    """Return *token* without the pair of quotes :mod:`shlex` keeps on Windows.

    PowerShell takes a path in double or in single quotes.
    """
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def platform_command(handler: dict[str, object], keys: tuple[str, ...]) -> str | None:
    """Return the command line *handler* runs, read from the tool's *keys*, or ``None``."""
    for key in keys:
        command = handler.get(key)
        if isinstance(command, str):
            return command
    return None


def owned_by_apothem(
    handler: dict[str, object],
    keys: tuple[str, ...],
    args_key: str | None,
    *,
    project_scope: bool = False,
) -> bool:
    """Return True when the line *handler* runs, as the tool reads it, is Apothem's.

    Only the tool's own *keys* are read, and its *args_key* (``None`` for a
    tool that reads no argument list), so a value the tool ignores never makes
    a handler look like Apothem's.
    """
    command = platform_command(handler, keys)
    if command is None:
        return False
    args = handler.get(args_key) if args_key is not None else None
    return is_apothem_hook(
        {"command": command, "args": args}, project_scope=project_scope
    )


def user_handlers(
    document: object, keys: tuple[str, ...], args_key: str | None
) -> Iterator[dict[str, object]]:
    """Yield every Apothem-owned hook handler mapping nested in *document*.

    For a file under the operator's own home. Ownership is read from the
    command line the handler runs (under the tool's *keys*), the one the probe
    starts. The walk keeps its own stack rather than recursing, so a document
    nested as deep as :func:`json.loads` accepts is read without running out
    of call depth.
    """
    pending: list[Iterator[object]] = [iter((document,))]
    while pending:
        node = next(pending[-1], _DONE)
        if node is _DONE:
            pending.pop()
        elif isinstance(node, dict):
            if owned_by_apothem(node, keys, args_key):
                yield node
            pending.append(iter(node.values()))
        elif isinstance(node, list):
            pending.append(iter(node))


def project_handlers(document: object) -> Iterator[dict[str, object]]:
    """Yield the hook handlers of a project hook file, where the tools read them.

    An event map, ``hooks.<event>[]``, holds handlers directly (GitHub Copilot,
    Cursor) or in matcher groups, ``hooks.<event>[].hooks[]`` (CodeBuddy and the
    Devin Local config). A list, ``hooks[]`` (Kiro), holds each command under the
    hook's ``action``. Nothing nested anywhere else is read, so a value an
    operator or a tool keeps beside a handler never counts as one.
    """
    if not isinstance(document, dict):
        return
    hooks = document.get("hooks")
    if isinstance(hooks, list):
        for hook in hooks:
            if isinstance(hook, dict) and isinstance(hook.get("action"), dict):
                yield hook["action"]
        return
    if not isinstance(hooks, dict):
        return
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            group = entry.get("hooks")
            if isinstance(group, list):
                yield from (handler for handler in group if isinstance(handler, dict))
            else:
                yield entry


def walk(folder: Path) -> Iterator[tuple[Path, str]]:
    """Yield each entry under *folder* as ``link``, ``folder`` or ``file``.

    A link is never followed, not even to tell whether it names a folder: it
    is told apart first, from the entry itself, and not descended into.

    Raises:
        OSError: A folder under *folder* cannot be listed.
    """
    pending = [folder]
    while pending:
        current = pending.pop()
        with os.scandir(current) as listing:
            entries = sorted(listing, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            if entry.is_symlink() or is_link(path):
                yield path, "link"
            elif entry.is_dir(follow_symlinks=False):
                yield path, "folder"
                pending.append(path)
            else:
                yield path, "file"
