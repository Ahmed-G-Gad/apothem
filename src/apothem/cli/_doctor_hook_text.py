# SPDX-License-Identifier: MIT

"""Read hook files and spell paths for ``doctor``'s hook probe.

The helpers here look at text and parsed JSON only, apart from :func:`walk`
and :func:`sha256_of`, which list and read a hook folder the probe already
trusts, and :func:`read_hook_file`, which reads one hook file. None of them
starts a program. :mod:`apothem.cli._doctor_hooks` uses them to find the hook
commands an install registered and to judge them.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path, PurePath
from typing import Final

from apothem.harnesses._shared.install_driver import is_apothem_hook
from apothem.lib.links import is_link

#: Marks the end of one level of :func:`user_handlers`'s walk.
_DONE = object()

#: The largest hook file doctor reads, in bytes; one the tool reads is far
#: smaller. A project's committers choose its size.
MAX_HOOK_FILE_BYTES: Final = 4 * 1024 * 1024

#: Bytes :func:`sha256_of` reads at a time.
_BLOCK_BYTES: Final = 1024 * 1024


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
    """
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(_BLOCK_BYTES), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


class HookFileTooLargeError(ValueError):
    """A hook file is larger than doctor reads (:data:`MAX_HOOK_FILE_BYTES`)."""


def read_hook_file(path: Path) -> str:
    """Return *path*'s text, reading no more than :data:`MAX_HOOK_FILE_BYTES`.

    Raises :class:`HookFileTooLargeError` for a larger file, :class:`OSError` when it
    cannot be read, and :class:`UnicodeDecodeError` when it is not UTF-8.
    """
    with path.open("rb") as handle:
        data = handle.read(MAX_HOOK_FILE_BYTES + 1)
    if len(data) > MAX_HOOK_FILE_BYTES:
        raise HookFileTooLargeError(path)
    return data.decode("utf-8")


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
