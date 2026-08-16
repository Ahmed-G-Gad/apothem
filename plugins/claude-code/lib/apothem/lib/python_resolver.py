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
   is populated and points at a real file.
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
    run under a WindowsApps stub). Falls back to a ``PATH`` walk that rejects
    Store shims. Raises :class:`RuntimeError` when no real interpreter can be
    found — the adapter surfaces that as an install-time failure rather than
    wiring a bare ``python`` that could resolve to a stub at hook-run time.
    """
    running = sys.executable
    if running:
        running_path = Path(running)
        if running_path.is_file() and not _is_windowsapps_stub(running_path):
            return running_path.resolve()

    resolved = _resolve_from_path()
    if resolved is not None:
        return resolved

    raise RuntimeError(
        "no real CPython >= 3.10 interpreter found for hook wiring; "
        "sys.executable is unusable and no PATH candidate satisfies the floor"
    )
