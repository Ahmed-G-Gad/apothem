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

from dataclasses import dataclass
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
    Registration,
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


@dataclass(frozen=True)
class _Plan:
    """What one install pass decided before it wrote anything."""

    registration: Registration
    fits: bool


#: The plan :func:`render_config` made, by config path, for the
#: :func:`_apply_extras` call of the same install pass. Both run inside one
#: locked install, render first; deciding once means the rules files follow
#: the decision the config was written with.
_PLANS: dict[str, _Plan] = {}


def _plan(config_path: Path, profile: dict[str, Any]) -> _Plan:
    """Decide how this pass registers the rules file, from the files on disk."""
    config = rules_file.read_config(config_path)
    body, _ = rules_file.rules_text(config_path.parent, profile)
    fits = rules_file.fits_somewhere(body, config, config_path.parent.parent)
    registration = plan_registration(
        config,
        apothem_entry=apothem_created_entry(config_path),
        fits=fits,
        editable=rules_file.editable(config_path),
    )
    return _Plan(registration, fits)


def render_config(config_path: Path, profile: dict[str, Any]) -> str:
    """Render ``openclaw.json`` for *profile* against the operator's file."""
    _PLANS.pop(str(config_path), None)
    plan = _plan(config_path, profile)
    _PLANS[str(config_path)] = plan
    return materialize_native_config(profile, registration=plan.registration)


def _apply_extras(
    config_path: Path, profile: dict[str, Any], dry_run: bool
) -> tuple[MaterializationResult, ...]:
    """Write the workspace rules files and report a hook left alone."""
    plan = _PLANS.pop(str(config_path), None) or _plan(config_path, profile)
    results = rules_file.apply(config_path, profile, dry_run, register=plan.fits)
    if plan.registration.reason is None:
        return results
    note = MaterializationResult(
        outcome="warning",
        operation="open_claw_hook_registration",
        path=str(config_path),
        message=plan.registration.reason,
    )
    return (note, *results)


install = make_native_config_install(
    _HARNESS_NAME,
    materialize_native_config,
    harness_id=_HARNESS_ID,
    materialize_at=render_config,
    extra_writes=ExtraWrites(targets=rules_file.targets, apply=_apply_extras),
)
