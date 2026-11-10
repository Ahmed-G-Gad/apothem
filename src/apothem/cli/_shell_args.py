# SPDX-License-Identifier: MIT

"""Paths quoted for a command line the operator copies into a shell.

A fix or a hint names a command such as ``apothem update --project <path>``.
The path is quoted so the command runs as printed in the shell the operator is
likely to use: POSIX shell quoting outside Windows; on Windows, double quotes,
which PowerShell and ``cmd`` both read, unless the path holds a character
PowerShell expands inside double quotes.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

#: Characters PowerShell expands inside double quotes (a variable, an escape).
_POWERSHELL_EXPANDS = ("$", "`")


def quoted_path(path: Path | str) -> str:
    """Return *path* quoted for the operator's shell.

    Outside Windows, :func:`shlex.quote`. On Windows, ``"<path>"``; a path
    with ``$`` or a backtick is put in PowerShell single quotes instead, with
    each ``'`` doubled, so PowerShell (the shell the Windows installer uses)
    reads it as written.
    """
    text = str(path)
    if os.name != "nt":
        return shlex.quote(text)
    if any(char in text for char in _POWERSHELL_EXPANDS):
        return "'" + text.replace("'", "''") + "'"
    return f'"{text}"'


__all__ = ["quoted_path"]
