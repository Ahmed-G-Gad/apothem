# SPDX-License-Identifier: MIT

"""Per-user state directory for hook handlers that keep per-session counters.

Why this module exists. The session-end gate and the proactive-compaction
tracker keep a small JSON file per session. They used to write under a fixed
subdirectory of the OS temp dir, created with default permissions and shared by
every user on the host, which let another local user read a session's counters
or pre-create the directory. This helper gives every stateful handler one
per-user location, created with mode ``0700``.

Resolution order (first that applies wins):

1. ``APOTHEM_HOOK_STATE_DIR``: an explicit operator or test override.
2. ``CLAUDE_PLUGIN_DATA``: the plugin's own data directory, which Claude Code
   exports to plugin hooks; state then lives under ``<data>/state``.
3. ``XDG_STATE_HOME``: ``<xdg>/apothem`` on hosts that set it.
4. The platform default: ``%LOCALAPPDATA%\\apothem\\state`` on Windows,
   ``~/.local/state/apothem`` elsewhere.

The helper is stdlib-only because the hook runtime ships without the
``apothem`` package on plugin-alone installs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

__all__ = ["OVERRIDE_ENV", "hook_state_dir", "session_key"]

#: Explicit override for the state root (operators and tests).
OVERRIDE_ENV: Final[str] = "APOTHEM_HOOK_STATE_DIR"

_ALLOWED_KEY_CHARS: Final[frozenset[str]] = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
_MAX_KEY_LENGTH: Final[int] = 128


def _state_root() -> Path:
    override = os.environ.get(OVERRIDE_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    if plugin_data:
        return Path(plugin_data).expanduser() / "state"
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "apothem"
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / "apothem" / "state"
    return Path.home() / ".local" / "state" / "apothem"


def hook_state_dir(name: str) -> Path:
    """Return the per-user state directory for the handler called *name*.

    The directory and every missing parent this call creates get mode
    ``0700``. An existing directory the current user owns is tightened to
    ``0700``. Errors are left to the caller, which is fail-open by contract.
    """
    path = _state_root() / name
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if hasattr(os, "getuid"):
        info = path.stat()
        if info.st_uid == os.getuid() and info.st_mode & 0o077:
            path.chmod(0o700)
    return path


def session_key(session_id: object) -> str:
    """Map a payload ``session_id`` to a safe, bounded filename stem.

    Keeps ``[A-Za-z0-9._-]`` only (no path traversal) and bounds the length.
    When the payload carries no usable id, the key falls back to the parent
    process id: the harness process that spawns every hook of one session, so
    two sessions without ids never share a counter.
    """
    if isinstance(session_id, str):
        cleaned = "".join(ch for ch in session_id if ch in _ALLOWED_KEY_CHARS)
        cleaned = cleaned.strip(".")[:_MAX_KEY_LENGTH]
        if cleaned:
            return cleaned
    return f"ppid-{os.getppid()}"
