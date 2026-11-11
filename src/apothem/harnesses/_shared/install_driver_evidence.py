# SPDX-License-Identifier: MIT

"""What on disk and in the ledger shows that Apothem installed at a root.

:func:`install_driver_lifecycle.detect_install` asks two questions here: does
a manifest entry's target hold something only Apothem produces
(:func:`_entry_proves_install`), and did an uninstall stop with Apothem's
files still in place (:func:`_unfinished_here`)?
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    complete_managed_block,
    extract_managed_block,
)
from apothem.lib.install_ledger import LedgerRecord
from apothem.lib.propagation import InstallEntry, resolve_target

from .install_driver_blocks import endless_block_left
from .install_driver_outcome import last_uninstall_finished
from .install_driver_pathsafety import _APOTHEM_SUBTREE, _holds_content
from .install_driver_written import still_written


def _carries_managed_block(target: Path, install_open: Callable[[], bool]) -> bool:
    """Return True when *target* holds an Apothem sentinel-delimited block.

    The managed block is self-delimiting and Apothem-specific, so finding one
    inside an operator-owned anchor is positive proof of an install even though
    the file itself is not Apothem's to own. A BEGIN marker whose END is gone
    counts unless the ledger shows the install was closed (*install_open*):
    the uninstall then runs, leaves that file as it is and names it, and once
    the install is closed the file no longer reads as installed.
    """
    if not target.is_file():
        return False
    try:
        text = target.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    if complete_managed_block(text) is not None:
        return True
    return extract_managed_block(text) is not None and install_open()


def _entry_proves_install(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
    install_open: Callable[[], bool],
) -> bool:
    """Return True when *entry*'s on-disk state proves Apothem installed here.

    Only *unambiguous* evidence counts — a surface Apothem alone can produce:

    * a ``sentinel_merge`` anchor carrying the Apothem managed block, and
    * a non-empty target under the Apothem-owned ``.apothem/`` subtree.

    Every other manifest target is deliberately NOT evidence. A target's
    ``ownership_class`` of ``apothem-owned`` says Apothem *manages* the path,
    not that Apothem *created* it: ``~/.claude/agents/``, ``~/.qwen/skills/``,
    and their siblings are surfaces the harness itself offers for
    operator-authored content, so their existence proves nothing. Neither does a
    ``write_text`` target on a vendor-owned config file such as
    ``~/.claude/settings.json``, which the harness writes for its own use.
    """
    target = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    if entry.mode == "sentinel_merge":
        return _carries_managed_block(target, install_open)
    return _APOTHEM_SUBTREE in target.parts and _holds_content(target)


def _unfinished_here(harness_name: str, root: Path) -> bool:
    """Return True when an unfinished uninstall left Apothem's files at *root*.

    *root*'s latest record is ``uninstall-incomplete`` and a file the active
    install lists still has the content Apothem wrote (see
    :func:`still_written`), a managed block lost its END marker (the retry
    then names that file), or no install is left since a finished uninstall
    (only a second run, which compares each path with what this release
    writes, can tell); an unreadable ledger reads as no evidence. With nothing
    Apothem wrote left, the install is closed by an ``uninstall``.
    """
    try:
        unfinished = install_ledger.unfinished_uninstall(harness_name, root=root)
        if unfinished is None:
            return False
        active = install_ledger.active_install_records(harness_name, root=root)
    except install_ledger.LedgerError:
        return False
    if not active and last_uninstall_finished(harness_name, root):
        return True
    if any(
        still_written(target) or endless_block_left(target)
        for install in active
        for target in install.targets
    ):
        return True
    with contextlib.suppress(OSError, install_ledger.LedgerError):
        install_ledger.append_record(
            LedgerRecord.create(
                harness=harness_name,
                root=root,
                kind="uninstall",
                install_id=unfinished.install_id,
            )
        )
    return False
