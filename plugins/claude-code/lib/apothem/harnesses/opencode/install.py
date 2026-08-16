# SPDX-License-Identifier: MIT

"""Install logic for the opencode harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_native_config_install
from apothem.harnesses.opencode.materializer import materialize_native_config

_HARNESS_NAME: str = "opencode"
_HARNESS_ID: str = "opencode"

install = make_native_config_install(
    _HARNESS_NAME,
    materialize_native_config,
    harness_id=_HARNESS_ID,
)
