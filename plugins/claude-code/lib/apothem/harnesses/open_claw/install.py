# SPDX-License-Identifier: MIT

"""Install logic for the open-claw harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_native_config_install
from apothem.harnesses.open_claw.materializer import materialize_native_config

_HARNESS_NAME: str = "open_claw"
_HARNESS_ID: str = "open-claw"

install = make_native_config_install(
    _HARNESS_NAME,
    materialize_native_config,
    harness_id=_HARNESS_ID,
)
