# SPDX-License-Identifier: MIT

"""Resolve a real CPython interpreter for install-time hook-command wiring.

The Claude Code ``settings.json`` hook entries must invoke a concrete
interpreter, never a bare ``python`` name that a host's ``PATH`` can resolve to
a Microsoft Store ``WindowsApps`` launcher stub (a zero-content shim that opens
the Store instead of running the script). This module supplies the absolute
interpreter path that the adapter substitutes for the template's
``${PYTHON_BIN}`` placeholder at install time.

Resolution order:

1. ``sys.executable`` — the interpreter running the install. apothem declares
   ``requires-python = ">=3.10"``, so a WindowsApps stub (which cannot import or
   run apothem at all) can never be the running interpreter; ``sys.executable``
   is therefore guaranteed a real CPython that satisfies the floor whenever it
   is populated and points at a real file. One ``WindowsApps`` path is exactly
   that real interpreter: the Microsoft Store build of CPython reports
   ``...\\Microsoft\\WindowsApps\\PythonSoftwareFoundation.Python.<version>_<id>\\
   python.exe`` (``PC/python_uwp.cpp`` in CPython), an app-execution alias. It
   is returned as reported, without the stub test, the size floor, or symlink
   resolution. The alias is a reparse point, not an ordinary executable file,
   so the size floor says nothing against it. It is not resolved because it is
   the path CPython reports and other processes launch, and what resolution
   does to a reparse point was not checked on Windows. Every other
   ``WindowsApps`` path stays rejected.
2. A ``PATH`` walk mirroring ``hooks/lib/find-python.sh`` — every candidate name
   probed in ``PATH`` order, ``WindowsApps`` shims and (on Windows)
   sub-1024-byte stubs rejected, each survivor version-probed against the
   floor. This is the
   fallback for the (rare) embedded / frozen case where ``sys.executable`` is
   unusable.

The PATH-walk fallback is the Python sibling of the shipped shell locators
(``find-python.sh`` / ``find-python.ps1``); it does not replace them — the
bootstrap stubs still consume the shell locators on the no-substitution path.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

# Minimum interpreter the hooks require, mirroring ``requires-python`` in
# ``pyproject.toml`` and the floor in ``hooks/lib/find-python.sh``.
MIN_MAJOR: Final[int] = 3
MIN_MINOR: Final[int] = 10

# Candidate executable names probed in ``PATH``, most-specific last so the
# bare names win when they already satisfy the floor (mirrors find-python.sh).
_CANDIDATE_NAMES: Final[tuple[str, ...]] = (
    "python",
    "python3",
    "python3.14",
    "python3.13",
    "python3.12",
    "python3.11",
    "python3.10",
)

# Minimum byte size for a real interpreter on Windows; WindowsApps launcher
# shims are near-empty reparse stubs well under this floor (mirrors
# find-python.sh). Windows-only: tiny POSIX shims (pyenv/asdf shell scripts)
# are legitimate interpreters and must not be rejected by size.
_MIN_INTERPRETER_BYTES: Final[int] = 1024

# Package family prefix of the Microsoft Store build of CPython, compared
# case-folded. The trailing dot keeps the Python install manager's own
# ``PythonSoftwareFoundation.PythonManager_*`` package out of the match.
_STORE_PACKAGE_PREFIX: Final[str] = "pythonsoftwarefoundation.python."

# Probe program: print ``"<major> <minor>"`` for the running interpreter.
_VERSION_PROBE: Final[str] = (
    "import sys; "
    "sys.stdout.write(str(sys.version_info.major) + chr(32) "
    "+ str(sys.version_info.minor))"
)


def _is_windows() -> bool:
    """Return True on Windows; the platform seam tests monkeypatch."""
    return os.name == "nt"


def _is_windowsapps_stub(path: Path) -> bool:
    """Return True when *path* is a Microsoft Store launcher shim.

    Store shims live under ``...\\Microsoft\\WindowsApps\\`` and are near-empty
    reparse stubs; either signal alone is conclusive, so both are rejected.
    The byte-size floor applies on Windows only — it exists for the
    WindowsApps stub problem, and a tiny POSIX shim (a pyenv/asdf shell
    script) is a real interpreter. An unstatable path is conservatively a
    stub on every platform.
    """
    if "WindowsApps" in path.parts:
        return True
    try:
        size = path.stat().st_size
    except OSError:
        return True
    return _is_windows() and size < _MIN_INTERPRETER_BYTES


def _is_store_python_alias(path: Path) -> bool:
    """Return True when *path* is the Microsoft Store CPython's own alias.

    The Store build reports ``sys.executable`` as
    ``<LocalAppData>\\Microsoft\\WindowsApps\\<package family>\\python.exe``. That
    file is an app-execution alias (a reparse point) and it is the interpreter
    running the process, so the stub and size tests do not apply to it. The
    shape is positive evidence only. The not-installed launcher stub (directly
    in ``WindowsApps``), the redirector's own package, other apps, the Python
    install manager, and the package install directory all fail it. The
    ``WindowsApps`` segment alone never matches. Names compare case-folded, as
    Windows paths do.
    """
    parts = path.parts
    if len(parts) < 4:
        return False
    microsoft, windowsapps, family, name = (part.casefold() for part in parts[-4:])
    return (
        microsoft == "microsoft"
        and windowsapps == "windowsapps"
        and family.startswith(_STORE_PACKAGE_PREFIX)
        and name.startswith("python")
        and name.endswith(".exe")
    )


def _probe_version(executable: Path) -> tuple[int, int] | None:
    """Return ``(major, minor)`` for *executable*, or None when unprobeable.

    Runs the candidate with a literal probe program (no shell, no untrusted
    input). Any failure — non-zero exit, unparseable output, OSError — yields
    None so the caller skips the candidate rather than aborting the walk.
    """
    try:
        completed = subprocess.run(  # noqa: S603 — literal argv, trusted probe program, no shell
            [str(executable), "-c", _VERSION_PROBE],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    parts = completed.stdout.strip().split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _satisfies_floor(major: int, minor: int) -> bool:
    """Return True when ``(major, minor)`` meets the ``>= 3.10`` floor."""
    return major > MIN_MAJOR or (major == MIN_MAJOR and minor >= MIN_MINOR)


def _path_candidates(name: str) -> list[Path]:
    """Return every executable named *name* found across ``PATH``, in order.

    The Python stand-in for ``find-python.sh``'s PATH walk: it lists *all*
    matches rather than only the first, so a WindowsApps shim early on ``PATH``
    does not mask a real interpreter found later. Empty ``PATH`` segments are
    skipped, not resolved to the current directory — a cwd-resident interpreter
    must never be discovered, version-probed (executed), and wired into the
    hook command (defense-in-depth, mirroring ``find-python.sh``).
    """
    found: list[Path] = []
    raw_path = os.environ.get("PATH", "")
    suffixes = [""]
    if os.name == "nt":
        pathext = os.environ.get("PATHEXT", ".EXE")
        suffixes = [""] + [ext.lower() for ext in pathext.split(os.pathsep) if ext]
    for directory in raw_path.split(os.pathsep):
        # Skip an empty PATH segment (a doubled separator, or a leading /
        # trailing one) rather than mapping it to cwd. POSIX resolves an empty
        # segment to the current directory, but this resolver's result is
        # version-probed (executed) and substituted for ``${PYTHON_BIN}`` in the
        # hook command that runs on every tool use; trusting a cwd interpreter
        # there is the footgun this guard closes. An explicit "." entry is
        # non-empty and still honored below.
        if not directory:
            continue
        for suffix in suffixes:
            candidate = Path(directory) / (name + suffix)
            if candidate.is_file() and os.access(candidate, os.X_OK):
                found.append(candidate)
    return found


def _resolve_from_path() -> Path | None:
    """Walk ``PATH`` for a real CPython satisfying the floor, or None.

    Mirrors ``find-python.sh``: probe each candidate name in priority order,
    reject WindowsApps shims (and, on Windows, sub-1024-byte stubs), and
    return the first interpreter whose probed version meets the floor.
    """
    for name in _CANDIDATE_NAMES:
        for candidate in _path_candidates(name):
            if _is_windowsapps_stub(candidate):
                continue
            version = _probe_version(candidate)
            if version is None:
                continue
            if _satisfies_floor(*version):
                return candidate.resolve()
    return None


def resolve_python_bin() -> Path:
    """Return the absolute path to a real CPython >= 3.10 for hook wiring.

    Prefers ``sys.executable`` (guaranteed a real, floor-satisfying interpreter
    whenever it is populated and points at a real file, because apothem cannot
    run under a WindowsApps stub). The Microsoft Store build of CPython reports
    its own ``WindowsApps`` alias there, which is returned as reported; any
    other ``WindowsApps`` path is skipped. Falls back to a ``PATH`` walk that
    rejects Store shims. Raises :class:`RuntimeError` when no real interpreter
    can be found — the adapter surfaces that as an install-time failure rather
    than wiring a bare ``python`` that could resolve to a stub at hook-run time.
    """
    running = sys.executable
    if running:
        running_path = Path(running)
        if running_path.is_file():
            if _is_store_python_alias(running_path):
                # Keep the alias path as reported: see the module docstring for
                # why it is neither size-checked nor resolved.
                return running_path.absolute()
            if not _is_windowsapps_stub(running_path):
                return running_path.resolve()

    resolved = _resolve_from_path()
    if resolved is not None:
        return resolved

    raise RuntimeError(
        "no real CPython >= 3.10 interpreter found for hook wiring; "
        "sys.executable is unusable and no PATH candidate satisfies the floor"
    )


def _short_path_name(long_path: str) -> str | None:
    """Return ``GetShortPathNameW`` of *long_path*, or None when the call fails.

    Windows only. The API is called twice, as its contract requires: first with
    no buffer to learn the length it needs, then with a buffer of that length.
    ``ctypes.WinDLL`` exists only on Windows, so the ignore below covers mypy on
    POSIX hosts and the ``unused-ignore`` code covers mypy on Windows.
    """
    kernel32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined, unused-ignore]
    get_short_path = kernel32.GetShortPathNameW
    get_short_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    get_short_path.restype = ctypes.c_uint32
    needed = get_short_path(long_path, None, 0)
    if needed == 0:
        return None
    buffer = ctypes.create_unicode_buffer(needed)
    written = get_short_path(long_path, buffer, needed)
    if written == 0 or written >= needed:
        return None
    return str(buffer.value)


def windows_short_path(path: Path) -> Path:
    """Return the Windows 8.3 short form of *path*, or *path* unchanged.

    A short form has no space, so it survives an unquoted command word. The
    API returns *path* itself when short-name generation is disabled on the
    volume, and returns 0 on failure; both leave *path* as given. Off Windows,
    and when the API cannot be reached, *path* is returned unchanged.
    """
    if not _is_windows():
        return path
    try:
        short = _short_path_name(str(path))
    except (AttributeError, OSError):
        return path
    return Path(short) if short else path
