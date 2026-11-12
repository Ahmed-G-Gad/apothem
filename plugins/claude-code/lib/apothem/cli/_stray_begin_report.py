# SPDX-License-Identifier: MIT

"""What a stray Apothem BEGIN marker means for ``verify`` and ``doctor`` output.

A BEGIN marker that starts no whole block, or a marker pair no rule can place,
in a file a tool's install keeps a managed block in, fails that tool's verify
(see :func:`apothem.harnesses._shared.install_driver_blocks.stray_begin_files`).
Install and update keep such a marker, so re-running them does not clear it.
A failed ``verify`` row and ``doctor``'s failed check name each such file and
say what to delete, so the fix is not a guess. Everything here reads files and
the install ledger and writes nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from apothem.cli._helpers import _Adapter, _harness_roots
from apothem.harnesses._shared.install_driver_blocks import (
    stray_begin_files,
    unclear_block_at,
    unclear_block_fix,
    unclear_block_text,
)
from apothem.lib.harness_registry import HarnessRegistryEntry


def stray_begin_paths(
    entry: HarnessRegistryEntry, adapter: _Adapter, project_root: Path | None
) -> list[Path]:
    """Return the files of *entry*'s install that hold a stray BEGIN marker.

    The roots are the ones the install driver checks (see :func:`_harness_roots`).
    Empty when there is none, and when the files cannot be listed: a
    project-scope tool without ``--project``, or a manifest the driver cannot
    load. The caller then keeps its generic message.
    """
    harness_root, scoped_project = _harness_roots(entry, adapter, project_root)
    if harness_root is None and scoped_project is None:
        return []
    try:
        return stray_begin_files(
            entry.package_key, harness_root=harness_root, project_root=scoped_project
        )
    except (OSError, RuntimeError, ValueError):
        return []


def stray_begin_note(files: Sequence[Path], *, then: str) -> str:
    """Return one line that names each of *files* and says how to clear its marker.

    The old Apothem text below the marker goes too: an install or update writes
    a whole block of its own apart from the marker, so that text only repeats
    Apothem's rules. A file whose marker pair no rule can place is named on its
    own, with the lines of its BEGIN marker and code block and the fix (see
    :func:`unclear_block_text`). *then* is the step that follows; both callers
    name an update, which writes Apothem's block back when the file holds none.
    """
    parts: list[str] = []
    stray: list[str] = []
    for path in files:
        where = unclear_block_at(path)
        if where is None:
            stray.append(str(path))
        else:
            parts.append(
                f"{unclear_block_text(path, where)}. {unclear_block_fix(where)}"
            )
    if stray:
        if len(stray) == 1:
            subject = f"{stray[0]} has"
        else:
            subject = f"{', '.join(stray[:-1])} and {stray[-1]} each have"
        parts.insert(
            0,
            f"{subject} an Apothem BEGIN marker with no END marker: delete that "
            "marker line and the old Apothem text below it by hand, keep your own "
            "lines",
        )
    return f"{'; '.join(parts)}, then {then}"
