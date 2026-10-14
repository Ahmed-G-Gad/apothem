# SPDX-License-Identifier: MIT

"""A ``python3`` for test subprocesses that runs the interpreter running the test.

An installer or an installed hook command that names ``python3`` runs the
first one on PATH, and that one belongs to the host. It can lack the test's
dependencies, carry a pip that installs into it, or not be an interpreter at
all: on Windows it is often the Microsoft Store "App execution alias", which
exits 49 and asks the user to install Python. Each turns a passing test into
a host-dependent failure.

:func:`write_python_shim` writes a POSIX ``sh`` script that execs
``sys.executable``. A test puts the directory holding it first on the
subprocess PATH, so ``python3`` means the interpreter running the test.

The shim execs rather than links: a venv interpreter finds its packages
through the ``pyvenv.cfg`` beside the path it was started from, so a symlink
placed elsewhere would run the base interpreter. On Windows, where Git Bash
runs the shim, the interpreter path is written with forward slashes and the
file with LF line endings.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Final

#: rwxr-xr-x: the shim must be executable for a PATH lookup to find it.
_SHIM_MODE: Final[int] = 0o755


def write_python_shim(shim: Path, *options: str) -> None:
    """Write *shim*, a script that runs this test's interpreter with *options*
    ahead of the arguments it is given."""
    command = shlex.join([Path(sys.executable).as_posix(), *options])
    # LF on every host: Windows would otherwise write CRLF, and sh would then
    # read the interpreter as "/bin/sh\r".
    shim.write_text(f'#!/bin/sh\nexec {command} "$@"\n', encoding="utf-8", newline="\n")
    shim.chmod(_SHIM_MODE)
