# SPDX-License-Identifier: MIT

"""Tell whether a path is itself a link: a symbolic link or a Windows junction.

The install write guard and the clean-slate routine both refuse to write or
remove through a link, so they share this one test. ``Path.is_symlink()`` is
False for a Windows junction, and ``Path.is_junction`` exists only from Python
3.12, so the reparse tag is read from ``lstat`` instead.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

__all__ = ["is_link"]

#: Bit set in the reparse tag of a Windows reparse point that names another
#: location: junctions, symbolic links and other name surrogates.
_NAME_SURROGATE_BIT = 0x20000000


def is_link(path: Path) -> bool:
    """Return True when *path* itself is a symbolic link or a Windows junction.

    A junction is a directory reparse point: ``is_symlink()`` is False for it
    and ``is_dir()`` is True. Any reparse point whose tag carries the
    name-surrogate bit names another location and counts too. A path that
    cannot be read is not a link.
    """
    if path.is_symlink():
        return True
    if sys.platform != "win32":
        return False
    try:
        tag = getattr(os.lstat(path), "st_reparse_tag", 0)
    except OSError:
        return False
    return bool(tag & _NAME_SURROGATE_BIT) or tag == stat.IO_REPARSE_TAG_MOUNT_POINT
