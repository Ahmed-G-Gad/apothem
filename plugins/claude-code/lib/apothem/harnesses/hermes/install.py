# SPDX-License-Identifier: MIT

"""Install logic for the hermes harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_native_config_install
from apothem.harnesses.hermes.materializer import (
    materialize_native_config,
    retired_entries,
)

_HARNESS_NAME: str = "hermes"
_HARNESS_ID: str = "hermes"

install = make_native_config_install(
    _HARNESS_NAME,
    materialize_native_config,
    harness_id=_HARNESS_ID,
    retired_fn=retired_entries,
)
