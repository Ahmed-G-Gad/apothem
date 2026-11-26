# SPDX-License-Identifier: MIT

"""What Apothem markers left to fix by hand mean for ``verify`` and ``doctor`` output.

A BEGIN marker that starts no whole block, two or more whole blocks, or a
marker pair no rule can place, in a file a tool's install keeps a managed
block in, fails that tool's verify (see
:func:`apothem.harnesses._shared.install_driver_blocks.stray_begin_files`).
Install and update keep such a marker, or leave such a file as it is (one
with marker pairs no rule can place while an install record lists it, or
rule 3 fired in it), so re-running them does not clear it. A failed
``verify`` row and ``doctor``'s failed check name each such file and give
the numbered steps that fix it, so the fix is not a guess, and say that
install and update leave the file as it is only where they do (see
:func:`record_lists`). For an OpenClaw rules file, which the update writes
only while it fits OpenClaw's per-file limit, the steps say so (see
:func:`size_limited`).
Everything here reads files and the install ledger and writes nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

from apothem.cli._helpers import _Adapter, _harness_roots
from apothem.harnesses._shared.install_driver_blocks import (
    stray_begin_files,
    text_at,
    unclear_pairs_at,
    whole_blocks_at,
)
from apothem.harnesses._shared.install_driver_blocktext import (
    FITS,
    REPLACES,
    not_back_text,
    stray_fix_text,
    stray_subject,
    two_blocks_report,
    unclear_block_report,
)
from apothem.harnesses._shared.install_driver_evidence import listed_in_record
from apothem.lib.harness_materializer import (
    lone_begins,
    stray_begins,
    uncertain_pairs,
    whole_blocks,
)
from apothem.lib.harness_registry import HarnessRegistryEntry


def stray_begin_paths(
    entry: HarnessRegistryEntry, adapter: _Adapter, project_root: Path | None
) -> list[Path]:
    """Return the files of *entry*'s install that hold Apothem markers to fix.

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


def markers_to_fix_by_hand(path: Path) -> bool:
    """Return True when *path* holds more than a BEGIN marker with no END marker.

    Two or more whole blocks, or marker pairs no rule can place: their text
    names each block or pair (see :func:`stray_begin_note`).
    """
    return len(whole_blocks_at(path)) > 1 or bool(unclear_pairs_at(path))


def _unlisted(path: Path) -> bool:
    """Return False: no install record lists *path*."""
    return False


def record_lists(
    entry: HarnessRegistryEntry, adapter: _Adapter, project_root: Path | None
) -> Callable[[Path], bool]:
    """Return whether an install record lists a file, as install and update read it.

    The lookup is the one the merge reads (see
    :func:`apothem.harnesses._shared.install_driver_evidence.listed_in_record`),
    at the root the install driver checks (see :func:`_harness_roots`): only
    while it lists a file do install and update leave a marker pair in code
    there as it is, apart from a pair that holds exactly the block they
    write, which they leave as it is with or without a record and which this
    lookup does not check. Without a root (a project-scope tool without
    ``--project``) no file is listed.
    """
    harness_root, scoped_project = _harness_roots(entry, adapter, project_root)
    root = harness_root if harness_root is not None else scoped_project
    if root is None:
        return _unlisted
    return partial(listed_in_record, entry.package_key, root)


def size_limited(entry: HarnessRegistryEntry) -> Callable[[Path], bool]:
    """Return whether the update writes a file of *entry*'s only while it fits a limit.

    True for every file of OpenClaw's (an install writes no other
    managed-block file for it than the rules file of each workspace, see
    :mod:`apothem.harnesses.open_claw.rules_file`), which the update leaves
    out of a workspace while it is over OpenClaw's per-file limit; False for
    any other tool's.
    """
    return _limited if entry.package_key == "open_claw" else _unlisted


def _limited(path: Path) -> bool:
    """Return True: the update writes *path* only while it fits a size limit."""
    return True


def _named(path: Path, text: str, listed: bool, outcome: str) -> str | None:
    """Return the text for *path* when its *text* holds more than a lone BEGIN marker.

    *listed* says whether an install record lists *path* (see
    :func:`record_lists`): only then, or for a pair that holds exactly the
    block they write (not checked here), do install and update leave a file
    with marker pairs in code as it is, so only then does its text say they
    do. *outcome* is what the next update does once a fix is made (see
    :func:`stray_begin_note`).
    """
    blocks = whole_blocks(text)
    if len(blocks) > 1:
        return two_blocks_report(path, text, blocks, left=False, outcome=outcome)
    pairs = uncertain_pairs(text)
    if pairs:
        return unclear_block_report(
            path,
            text,
            pairs,
            outcome=outcome,
            left=False,
            lone=lone_begins(text),
            held=listed,
        )
    return None


def stray_begin_note(
    files: Sequence[Path],
    *,
    then: str,
    listed: Callable[[Path], bool] = _unlisted,
    limited: Callable[[Path], bool] = _unlisted,
) -> str:
    """Return one line that names each of *files* and says how to clear its marker.

    A file with a BEGIN marker that starts no whole block gets its own text:
    the marker by its line, and a numbered step that changes that line (see
    :func:`stray_fix_text`). The old Apothem text below the marker is the
    operator's to delete: an install or update writes a whole block of its
    own apart from the marker, so that text only repeats Apothem's rules. The text says not to add the END
    marker back instead (see :func:`not_back_text`): once an install or
    update has written Apothem's block apart from the marker, the file would
    then hold two Apothem blocks, and before that, with a line of the
    operator's between the two markers, the next run replaces or takes out
    that line. A file with two or more whole blocks, or whose marker pairs
    no rule can place, is named on its own, with each block or pair, where
    its marker lines read, and how to fix it (see :func:`two_blocks_report`
    and :func:`unclear_block_report`). *then* is the step that follows; both
    callers name an update, which writes Apothem's block back when the file
    holds none. *listed* says whether an install record lists a file (see
    :func:`record_lists`); without it, the text for marker pairs says that
    install and update leave a file as it is only for the pair rule 3 fired
    on, which holds the file back with or without one. *limited* says
    whether the update writes a file only while it fits a size limit (see
    :func:`size_limited`); the steps for such a file say the update writes
    Apothem's block only if the file then fits.
    """
    parts: list[str] = []
    for path in files:
        text = text_at(path)
        outcome = FITS if limited(path) else REPLACES
        named = _named(path, text, listed(path), outcome)
        if named is not None:
            parts.append(named)
            continue
        strays, blocks = stray_begins(text), whole_blocks(text)
        parts.extend(
            [
                f"{path} has {stray_subject(text, strays=strays)} with no END marker.",
                stray_fix_text(text, outcome, strays=strays, blocks=blocks),
                not_back_text(text, blocks=blocks),
            ]
        )
    return " ".join([*(part for part in parts if part), f"Then {then}"])
