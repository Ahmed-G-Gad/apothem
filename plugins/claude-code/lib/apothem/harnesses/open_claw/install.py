# SPDX-License-Identifier: MIT

"""Install logic for the open-claw harness adapter.

Besides the native config and the support tree, the install writes the
Apothem rules file into each agent workspace and registers it with OpenClaw's
``bootstrap-extra-files`` hook (see
:mod:`apothem.harnesses.open_claw.rules_file`). How the hook entry is written
depends on what the operator's ``openclaw.json`` already holds, so the config
is rendered from that file as well as the profile; a reason the install left
the hook alone is reported as a warning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apothem.harnesses._shared.install_driver import MaterializationResult
from apothem.harnesses._shared.install_driver_ownership import current_target
from apothem.harnesses._shared.wrapper_factories import (
    ExtraWrites,
    make_native_config_install,
)
from apothem.harnesses.open_claw import rules_file
from apothem.harnesses.open_claw.materializer import (
    ENTRY_PATH,
    materialize_native_config,
    plan_registration,
)

_HARNESS_NAME: str = "open_claw"
_HARNESS_ID: str = "open-claw"


def apothem_created_entry(config_path: Path) -> bool:
    """Return True when the install record says Apothem created the hook entry.

    That is the case when the record lists a container Apothem created on the
    way to (or at) the entry: the entry then holds nothing of the operator's.
    """
    recorded = current_target(_HARNESS_NAME, config_path.parent, config_path)
    if recorded is None or not recorded.owned:
        return False
    return any(
        owned.kind == "container" and ENTRY_PATH[: len(owned.path)] == owned.path
        for owned in recorded.owned
    )


def render_config(config_path: Path, profile: dict[str, Any]) -> str:
    """Render ``openclaw.json`` for *profile* against the operator's file."""
    registration = plan_registration(
        rules_file.read_config(config_path),
        apothem_entry=apothem_created_entry(config_path),
    )
    return materialize_native_config(profile, registration=registration)


def _apply_extras(
    config_path: Path, profile: dict[str, Any], dry_run: bool
) -> tuple[MaterializationResult, ...]:
    """Write the workspace rules files and report a hook left alone.

    This runs after the config is written, before the install record is
    updated. A registration the install just wrote reads back as an enabled
    entry naming the file, so it raises no warning; a reason that kept the
    install from registering (the operator's own settings) still holds.
    """
    registration = plan_registration(
        rules_file.read_config(config_path),
        apothem_entry=apothem_created_entry(config_path),
    )
    results = rules_file.apply(config_path, profile, dry_run)
    if registration.reason is None:
        return results
    note = MaterializationResult(
        outcome="warning",
        operation="open_claw_hook_registration",
        path=str(config_path),
        message=registration.reason,
    )
    return (note, *results)


install = make_native_config_install(
    _HARNESS_NAME,
    materialize_native_config,
    harness_id=_HARNESS_ID,
    materialize_at=render_config,
    extra_writes=ExtraWrites(targets=rules_file.targets, apply=_apply_extras),
)
