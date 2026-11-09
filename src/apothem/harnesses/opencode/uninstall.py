# SPDX-License-Identifier: MIT

"""Uninstall logic for the opencode harness adapter."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_homelink import _names_same_folder
from apothem.harnesses._shared.install_driver_sharedlock import shared_scope
from apothem.harnesses._shared.wrapper_factories import make_native_config_uninstall
from apothem.harnesses.opencode.install import refuse_link_leaving_home
from apothem.harnesses.opencode.materializer import (
    _default_spellings,
    materialize_native_config,
    relocated_entries,
    retired_entries,
)
from apothem.lib import atomic_io, install_ledger
from apothem.lib.install_ledger import LedgerRecord

_HARNESS_NAME: str = "opencode"

#: The ``$schema`` value the install writes into ``opencode.json``.
_SCHEMA: str = "https://opencode.ai/config.json"

# The native ``opencode.json`` is rendered by the materializer rather than the
# manifest, so it is cleaned surgically: only the entries the install ledger
# records as Apothem's (``$schema`` and ``instructions`` when Apothem added
# them, the MCP servers it wrote) are stripped from the parsed operator JSON —
# operator keys, operator MCP servers and operator ``instructions`` entries
# survive — and the file is deleted only when Apothem created it and nothing
# operator-authored remains. An install recorded before ownership tracking also
# loses the ``instructions`` glob earlier releases wrote, and an MCP server
# converted to OpenCode 2's ``mcp.servers`` shape goes, as a whole, when its
# ``mcp.<name>`` is gone and it matches what Apothem wrote
# (``relocated_entries``). The pre-mutation file
# is copied into the Apothem backup root; no whole-file ``.bak`` sibling is
# left beside the operator's file. The manifest support subtree is then cleaned
# child-by-child by the shared driver.
_uninstall = make_native_config_uninstall(
    _HARNESS_NAME,
    materialize_native_config,
    retired_fn=retired_entries,
    relocated_fn=relocated_entries,
)


@install_driver.backup_session()
def uninstall(output_path: Path) -> install_driver.MaterializationRun:
    """Remove the OpenCode install at *output_path*'s folder.

    Refused, before anything is removed, when a link leads that folder out of
    the home (see :func:`~apothem.harnesses.opencode.install.refuse_link_leaving_home`).
    An install recorded under another spelling of the same folder
    (``~/.config/opencode``, when ``XDG_CONFIG_HOME`` names the folder a
    ``~/.config`` link leads to) is removed with it (see
    :func:`_finish_same_folder_install`).

    Returns the run of every removal. A removal that fails, or another run
    holding the install lock past its timeout, is an ``error`` result in it;
    the installs at the other spelling then stay recorded and the uninstall
    can be run again.

    Raises:
        MaterializationError: When a link leads the folder out of the home;
            nothing was removed.
    """
    refuse_link_leaving_home(output_path, uninstall=True)
    root = output_path.parent
    # Which spellings name this folder is read before the uninstall: it may
    # remove the folder, and the spellings are then compared by their resolved
    # paths, which do not fold case on a case-insensitive macOS volume.
    spellings = _same_folder_spellings(root)
    results = list(_uninstall(output_path).results)
    # The install lock is keyed by the resolved folder, so it is the one an
    # install at either spelling takes; the user-level lock goes outside it,
    # as an install takes them. The installs are re-read inside the locks.
    try:
        with (
            shared_scope(_HARNESS_NAME),
            atomic_io.advisory_lock(
                install_driver._install_lock_path(_HARNESS_NAME, root)
            ),
        ):
            for spelling in spellings:
                active = _active_installs(spelling)
                if active:
                    results.extend(_finish_same_folder_install(spelling, active, root))
    except TimeoutError as exc:
        results.append(
            install_driver._result(
                "error",
                "opencode_uninstall",
                root,
                f"another Apothem run holds the install lock: {exc}",
            )
        )
    return install_driver.MaterializationRun(
        harness=_HARNESS_NAME, dry_run=False, results=tuple(results)
    )


def _same_folder_spellings(root: Path) -> list[Path]:
    """Return the other spellings that name *root*'s folder."""
    return [
        spelling
        for spelling in _default_spellings()
        if str(spelling) != str(root) and _names_same_folder(spelling, root)
    ]


def _active_installs(spelling: Path) -> list[LedgerRecord]:
    """Return the active installs recorded at *spelling*; none when unreadable."""
    try:
        return install_ledger.active_install_records(_HARNESS_NAME, root=spelling)
    except (OSError, ValueError):
        return []


def _finish_same_folder_install(
    spelling: Path, active: list[LedgerRecord], root: Path
) -> list[install_driver.MaterializationResult]:
    """Remove what the installs recorded at *spelling* left in *root*, then close them.

    *spelling* names the folder *root* names, so the support files are gone
    with the uninstall at *root*. What is left is the managed block of each
    anchor the latest install wrote (the profile document), an
    ``opencode.json`` it created that now holds only the ``$schema`` and an
    empty ``instructions`` list, and the folders the installs created. The
    file is backed up, then each goes through the write guard at *root*; a
    folder goes only once empty. An uninstall record that names the backups
    closes the installs at *spelling*; when a removal fails it is an
    ``uninstall-incomplete`` record instead, and the installs stay recorded. The data stores need no step here:
    with *spelling* naming this folder they are the ones the uninstall at
    *root* already handled. A folder the installs created at a user-level
    path outside *root* is left (OpenCode writes none). Returns every
    removal's result.
    """
    record = active[-1]
    allowed = install_driver._allowed_write_root(root, None)
    results: list[install_driver.MaterializationResult] = []
    for target in record.targets:
        here = _respelled(Path(target.path), spelling, root)
        if here is None:
            continue
        if target.mode == "sentinel_merge":
            removal = install_driver._surgical_remove_from_target(
                here,
                "",
                mode="sentinel_merge",
                install_root=root,
                harness_name=_HARNESS_NAME,
                allowed_root=allowed,
            )
            if removal is not None:
                results.append(removal)
        elif here == root / "opencode.json" and target.created and _skeleton(here):
            results.append(_remove_skeleton(here, root=root, allowed=allowed))
    created = {
        here
        for install in active
        for path in install.created_dirs
        if (here := _respelled(Path(path), spelling, root)) is not None
    }
    results.extend(install_driver.remove_created_dirs(created, allowed_root=allowed))
    failed = any(result.outcome == "error" for result in results)
    install_ledger.append_record(
        LedgerRecord.create(
            harness=_HARNESS_NAME,
            root=spelling,
            kind="uninstall-incomplete" if failed else "uninstall",
            targets=install_driver.backup_ledger_targets(results),
            install_id=record.install_id,
        )
    )
    return results


def _respelled(path: Path, spelling: Path, root: Path) -> Path | None:
    """Return *path*, recorded below *spelling*, spelled below *root*."""
    try:
        return root / path.relative_to(spelling)
    except ValueError:
        return None


def _remove_skeleton(
    config: Path, *, root: Path, allowed: Path
) -> install_driver.MaterializationResult:
    """Back *config* up, then delete it; the result names the backup."""
    try:
        backup = install_driver.backup_existing(
            config, install_root=root, harness_name=_HARNESS_NAME, allowed_root=allowed
        )
    except OSError as exc:
        return install_driver.MaterializationResult(
            outcome="error",
            operation="surgical_uninstall",
            path=str(config),
            message=f"could not back up {config}: {exc}",
        )
    removal = install_driver._guarded_unlink(
        config, allowed_root=allowed, operation="surgical_uninstall"
    )
    if backup is None or removal.outcome == "error":
        return removal
    return replace(removal, backup_path=str(backup))


def _skeleton(config: Path) -> bool:
    """Return True when *config* holds only Apothem's ``$schema`` and no entries."""
    try:
        document = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(document, dict) or not set(document) <= {
        "$schema",
        "instructions",
    }:
        return False
    return document.get("$schema", _SCHEMA) == _SCHEMA and not document.get(
        "instructions", []
    )
