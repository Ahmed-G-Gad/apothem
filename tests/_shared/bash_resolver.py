# SPDX-License-Identifier: MIT

"""Shared resolver for a bash executable usable by test subprocesses.

On Windows hosts ``shutil.which("bash")`` can resolve to the WSL launcher
(``...\\Microsoft\\WindowsApps\\bash.EXE`` or the legacy ``System32`` shim),
which forwards into a WSL distribution: Windows-style script paths passed as
arguments are not translated for the guest (``C:\\Users\\...`` arrives
mangled) and the invocation fails with exit 127. Git for Windows ships a
native bash that accepts Windows paths, so tests that shell out to bash MUST
resolve the executable through :func:`find_test_bash` instead of calling
``shutil.which("bash")`` directly.

Resolution order:

1. POSIX hosts — ``shutil.which("bash")``, unchanged.
2. Windows — a git-bash derived from ``shutil.which("git")`` (the
   ``bin/bash.exe`` / ``usr/bin/bash.exe`` siblings under the Git install
   root), then the well-known Git-for-Windows install locations, then a PATH
   ``bash`` only when it is not a WSL launcher.

:func:`find_test_bash` returns ``None`` when no usable bash exists; callers
skip with :data:`SKIP_REASON` so the suite reports one uniform reason.

The Windows-only installer gates (``tests/integration/test_installer_verify_tag.py``
and ``tests/integration/test_clean_machine_install.py``) deliberately keep
their own ``sys.platform == "win32"`` skip: they exercise the POSIX
``install.sh`` end-to-end, for which ``install.ps1`` is the Windows path, so
a usable git-bash does not make them Windows-runnable.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Final

SKIP_REASON: Final[str] = (
    "no usable bash on this host (a PATH bash resolving to the WSL launcher "
    "is rejected, and no git-bash was found)"
)

# Well-known Git-for-Windows bash locations, probed when git itself is not on
# PATH.
_WINDOWS_BASH_FALLBACKS: Final[tuple[Path, ...]] = (
    Path("C:/Program Files/Git/bin/bash.exe"),
    Path("C:/Program Files/Git/usr/bin/bash.exe"),
)

# Path components that mark a Windows ``bash.exe`` as the WSL launcher rather
# than a native bash (the Store alias and the legacy System32 shim).
_WSL_LAUNCHER_PARTS: Final[frozenset[str]] = frozenset(
    {"windowsapps", "system32", "sysnative"}
)


def _is_wsl_launcher(bash: Path) -> bool:
    """Return True when *bash* is the Windows WSL launcher, not a native bash."""
    return any(part.lower() in _WSL_LAUNCHER_PARTS for part in bash.parts)


def _git_bash_candidates() -> list[Path]:
    """Candidate git-bash paths: git-derived siblings, then known locations.

    Git for Windows exposes ``git`` from ``<root>/cmd/``, ``<root>/bin/``, or
    ``<root>/mingw64/bin/``; in every layout the bash executables live at
    ``<root>/bin/bash.exe`` and ``<root>/usr/bin/bash.exe``, so the nearest
    three ancestors of the resolved ``git`` cover all shapes.
    """
    candidates: list[Path] = []
    git = shutil.which("git")
    if git is not None:
        for ancestor in list(Path(git).resolve().parents)[:3]:
            candidates.append(ancestor / "bin" / "bash.exe")
            candidates.append(ancestor / "usr" / "bin" / "bash.exe")
    candidates.extend(_WINDOWS_BASH_FALLBACKS)
    return candidates


def find_test_bash() -> str | None:
    """Resolve a bash executable that can run repo scripts, or ``None``.

    On POSIX this is exactly ``shutil.which("bash")``. On Windows a native
    git-bash is preferred and the WSL launcher is never returned.
    """
    if sys.platform != "win32":
        return shutil.which("bash")
    for candidate in _git_bash_candidates():
        if candidate.is_file():
            return str(candidate)
    which_bash = shutil.which("bash")
    if which_bash is not None and not _is_wsl_launcher(Path(which_bash)):
        return which_bash
    return None
