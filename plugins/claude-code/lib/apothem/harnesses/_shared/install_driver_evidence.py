# SPDX-License-Identifier: MIT

"""What on disk and in the ledger shows that Apothem installed at a root.

:func:`install_driver_lifecycle.detect_install` asks two questions here: does
a manifest entry's target hold something only Apothem produces
(:func:`_entry_proves_install`), and did an uninstall stop with Apothem's
files still in place (:func:`_unfinished_here`)? An install or update asks a
third before it merges Apothem's block into a file: does an install record
list that file (:func:`entry_prior`)? All three read the record the same way.
A verify or detect also asks whether a native config still parses
(:func:`_native_config_parses`): one that does not reads as not installed.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path

import yaml

from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    complete_managed_block,
    extract_managed_block,
    uncertain_block,
)
from apothem.lib.install_ledger import LedgerRecord
from apothem.lib.propagation import InstallEntry, resolve_target

from .install_driver_blocks import markers_left
from .install_driver_keys import one_install
from .install_driver_outcome import end_other_spellings, last_uninstall_finished
from .install_driver_ownership import LEGACY_OWNERSHIP, PriorOwnership, prior_ownership
from .install_driver_pathsafety import _APOTHEM_SUBTREE, _holds_content
from .install_driver_written import still_written


def _native_config_parses(target: Path) -> bool:
    """Return True unless *target* is a structurally invalid JSON/YAML file.

    Only ``.json``/``.yaml``/``.yml`` targets are parsed; other suffixes (e.g.
    Markdown anchors) pass trivially. A ``.json`` target may be JSONC or JSON5
    (OpenCode and OpenClaw read those dialects, and install leaves such a file
    in place when it has nothing to change). A present-but-corrupt config reads
    as not-installed.
    """
    from apothem.lib import lenient_json

    suffix = target.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        return True
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    try:
        if suffix == ".json":
            lenient_json.loads(text)
        else:
            yaml.safe_load(text)
    except (lenient_json.LenientJSONError, yaml.YAMLError):
        return False
    return True


def listed_in_record(harness_name: str, root: Path, target: Path) -> bool:
    """Return True when the current install record at *root* lists *target*.

    The install is the one the uninstall removes (see :func:`one_install`), so
    a file its records under the folder's other spellings list counts too, as
    the uninstall then reads it as recorded. An unreadable ledger reads as
    listed, as :func:`install_driver_blocks.install_may_be_open` reads it as
    open: nothing then shows that the install is gone, so the file's marker
    pair keeps counting, and the uninstall reaches the ledger and reports it
    instead of finding nothing installed.
    """
    try:
        active = one_install(harness_name, root)[0]
    except (install_ledger.LedgerError, OSError):
        return True
    wanted = str(target)
    return bool(active) and any(entry.path == wanted for entry in active[-1].targets)


def block_prior(harness_name: str, root: Path, target: Path) -> PriorOwnership:
    """Return what a merge of Apothem's block into *target* reads of its record.

    A managed-block file carries no owned entries: what the merge reads (see
    :func:`install_driver_ownership.fold_block`) is whether an install
    record lists the file, and it reads that as detection and the uninstall
    do (:func:`listed_in_record`): under every spelling of the folder, an
    unreadable ledger counting as a record. Otherwise an install under a
    spelling whose newest record leaves the file out would read a marker
    pair in code there as text of the operator's and add a second block,
    while the uninstall takes that pair for Apothem's block.
    :data:`LEGACY_OWNERSHIP` stands for a record that lists the file.
    """
    return LEGACY_OWNERSHIP if listed_in_record(harness_name, root, target) else ()


def entry_prior(
    mode: str, harness_name: str, root: Path, target: Path
) -> PriorOwnership:
    """Return what Apothem owned in *target*, which an entry of *mode* writes.

    A managed-block file (``sentinel_merge``) reads :func:`block_prior`, any
    other file :func:`install_driver_ownership.prior_ownership`.
    """
    if mode == "sentinel_merge":
        return block_prior(harness_name, root, target)
    return prior_ownership(harness_name, root, target)


def _carries_managed_block(
    target: Path,
    install_open: Callable[[], bool],
    listed: Callable[[Path], bool] | None = None,
) -> bool:
    """Return True when *target* holds an Apothem sentinel-delimited block.

    The managed block is self-delimiting and Apothem-specific, so finding one
    inside an operator-owned anchor is positive proof of an install even though
    the file itself is not Apothem's to own. A BEGIN marker whose END is gone
    counts unless the ledger shows the install was closed (*install_open*):
    the uninstall then runs, leaves that file as it is and names it, and once
    the install is closed the file no longer reads as installed. A marker
    pair no rule can place (see :func:`uncertain_block`), such as Apothem's
    block in a code block of the operator's, counts only while the current
    install record lists the file (*listed*, which an unreadable ledger
    passes): a file Apothem never wrote may quote the markers in a code
    example. The markers are ASCII, so a file
    that is not UTF-8 is read with its bad bytes replaced: the uninstall then
    reaches the step that says how to fix it, instead of a decoding error.
    """
    if not target.is_file():
        return False
    try:
        text = target.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    if complete_managed_block(text) is not None:
        return True
    if extract_managed_block(text) is not None and install_open():
        return True
    return listed is not None and uncertain_block(text) is not None and listed(target)


def _entry_proves_install(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
    install_open: Callable[[], bool],
    listed: Callable[[Path], bool] | None = None,
) -> bool:
    """Return True when *entry*'s on-disk state proves Apothem installed here.

    Only *unambiguous* evidence counts — a surface Apothem alone can produce:

    * a ``sentinel_merge`` anchor carrying the Apothem managed block (or a
      marker pair no rule can place, while the install record lists it, see
      :func:`_carries_managed_block`), and
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
        return _carries_managed_block(target, install_open, listed)
    return _APOTHEM_SUBTREE in target.parts and _holds_content(target)


def _unfinished_here(harness_name: str, root: Path) -> bool:
    """Return True when an unfinished uninstall left Apothem's files at *root*.

    *root*'s latest record is ``uninstall-incomplete`` and a file the active
    install lists still has the content Apothem wrote (see
    :func:`still_written`), a managed block lost its END marker or holds a
    marker pair no rule can place (the retry then names that file, see
    :func:`markers_left`), or no install is left since a finished uninstall
    (only a second run, which compares each path with what this release
    writes, can tell); an unreadable ledger reads as no evidence. The install
    is the one the uninstall removes (see :func:`one_install`), so the files
    its records under the folder's other spellings list count too. With
    nothing Apothem wrote left, the install is closed by an ``uninstall``, and
    so is the install under each of those spellings (see
    :func:`end_other_spellings`), as a finished uninstall closes them. This
    is a check (status, verify, detect), so closing is a side effect it
    never fails on: an error writing a record leaves the uninstall unfinished,
    to close on a later check, and a refusal of the real-home guard is
    dropped here too, quietly, while the guard logs it for the test run to
    report (see :func:`apothem.lib.home_write_guard.refusals`). An uninstall
    that ends those spellings itself raises the refusal instead.
    """
    try:
        unfinished = install_ledger.unfinished_uninstall(harness_name, root=root)
        if unfinished is None:
            return False
        active, same = one_install(harness_name, root)
    except (install_ledger.LedgerError, OSError):
        return False
    if not active and last_uninstall_finished(harness_name, root):
        return True
    if any(
        still_written(target) or markers_left(target)
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
        end_other_spellings(harness_name, same)
    return False
