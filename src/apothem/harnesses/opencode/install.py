# SPDX-License-Identifier: MIT

"""Install logic for the opencode harness adapter."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from apothem.harnesses._shared import install_driver_pathsafety
from apothem.harnesses._shared.install_driver import (
    MaterializationResult,
    MaterializationRun,
)
from apothem.harnesses._shared.wrapper_factories import make_native_config_install
from apothem.harnesses.opencode.materializer import (
    install_notes,
    materialize_native_config,
    relocated_entries,
    retired_entries,
)

_HARNESS_NAME: str = "opencode"
_HARNESS_ID: str = "opencode"

_install = make_native_config_install(
    _HARNESS_NAME,
    materialize_native_config,
    harness_id=_HARNESS_ID,
    retired_fn=retired_entries,
    relocated_fn=relocated_entries,
)


def refuse_link_leaving_home(
    output_path: Path, *, dry_run: bool = False, uninstall: bool = False
) -> None:
    """Raise when the folder of *output_path* is led out of the home by a link.

    The write guard walks up only to the folder above the install root, so a
    link higher up (``XDG_CONFIG_HOME=~/a/b`` with ``~/a`` leading out of the
    home) is found here instead (see
    :func:`~apothem.harnesses._shared.install_driver_pathsafety.refuse_link_leaving_home`).

    Raises:
        MaterializationError: When there is such a link; nothing is written
            or removed.
    """
    install_driver_pathsafety.refuse_link_leaving_home(
        _HARNESS_NAME,
        output_path.parent,
        operation="opencode_config",
        uninstall=uninstall,
        dry_run=dry_run,
    )


def install(
    output_path: Path, profile: dict[str, Any], *, dry_run: bool = False
) -> MaterializationRun:
    """Install into OpenCode's config folder, then report what keeps it unloaded.

    Refuses a folder a link leads out of the home (see
    :func:`refuse_link_leaving_home`), runs the shared native-config install,
    then puts one ``warning`` result first for each setting that keeps
    OpenCode from loading the install as written (see
    :func:`~apothem.harnesses.opencode.materializer.install_notes`). The
    warnings change no file and no install record.
    """
    refuse_link_leaving_home(output_path, dry_run=dry_run)
    run = _install(output_path, profile, dry_run=dry_run)
    warnings = tuple(
        MaterializationResult(
            outcome="warning",
            operation="opencode_config",
            path=str(output_path),
            message=message,
        )
        for message in install_notes(output_path.parent, profile)
    )
    if not warnings:
        return run
    return replace(run, results=(*warnings, *run.results))
