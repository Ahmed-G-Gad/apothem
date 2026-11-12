# SPDX-License-Identifier: MIT

"""Quote a folder for a command the operator pastes into a shell.

Every command Apothem prints that names a folder (doctor's fixes, verify's
note, quickstart's next step, uninstall's release steps) quotes it with
:func:`shell_quoted`, or gives the steps in words when it returns ``None``.
The module imports nothing from Apothem, so any layer can use it.
"""

from __future__ import annotations

import os
import unicodedata

__all__ = ["shell_quoted"]

#: What the quotes around a printed folder cannot carry, besides a control
#: character. Windows prints double quotes, inside which PowerShell expands
#: ``$`` and the backquote (and also reads the curly double quotes as quotes)
#: and cmd expands ``%`` and ``!``. Elsewhere single quotes, which a single
#: quote ends, and in PowerShell also the curly single quotes.
_UNQUOTABLE = {
    True: frozenset('$`%!"' + "".join(map(chr, (0x201C, 0x201D, 0x201E)))),
    False: frozenset("'" + "".join(map(chr, (0x2018, 0x2019, 0x201A, 0x201B)))),
}

#: What cmd acts on in a Windows folder that holds no space. PowerShell and
#: Git Bash pass such a folder without its quotes to a ``.cmd`` launcher (the
#: installer's ``apothem.cmd`` shim, or ``npx.cmd``), and the ``cmd.exe`` that
#: starts the launcher acts on these characters before the launcher runs.
#: With a space in the folder they keep the quotes, and cmd leaves these alone.
_CMD_METACHARACTERS = frozenset("&^|<>")


def shell_quoted(path: str, *, windows: bool | None = None) -> str | None:
    """Return *path* quoted for a command the operator pastes into a shell.

    On Windows (*windows*, by default this host) the path goes in double
    quotes, with each trailing backslash doubled so the closing quote stays a
    quote (``C:\\`` becomes ``"C:\\\\"``). cmd and Git Bash then pass one
    backslash; PowerShell passes both, which names the same folder once the
    path is resolved (``pathlib`` folds them), so compare resolved paths, not
    the raw argument. Elsewhere the path goes in single quotes.

    ``None`` when those quotes cannot carry the path (see
    :data:`_UNQUOTABLE`); on Windows also when a path with no space holds a
    character cmd acts on (see :data:`_CMD_METACHARACTERS`); when two
    backslashes stand together before its end (on Windows, as at the start of
    a network share ``\\\\server\\share``, Git Bash reads them as one inside
    double quotes; elsewhere fish reads them as one inside single quotes); and
    elsewhere also when it ends in a backslash, which escapes fish's closing
    quote.
    """
    windows = os.name == "nt" if windows is None else windows
    if any(
        char in _UNQUOTABLE[windows] or unicodedata.category(char) == "Cc"
        for char in path
    ):
        return None
    bare = path.rstrip("\\")
    if "\\\\" in bare:
        return None
    if not windows:
        return None if bare != path else f"'{path}'"
    if " " not in path and not _CMD_METACHARACTERS.isdisjoint(path):
        return None
    return '"' + bare + "\\" * (2 * (len(path) - len(bare))) + '"'
