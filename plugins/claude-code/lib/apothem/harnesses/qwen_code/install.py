# SPDX-License-Identifier: MIT

"""Install logic for the qwen-code harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_native_config_install
from apothem.harnesses.qwen_code.materializer import materialize_native_config

_HARNESS_NAME: str = "qwen_code"
_HARNESS_ID: str = "qwen-code"

install = make_native_config_install(
    _HARNESS_NAME,
    materialize_native_config,
    harness_id=_HARNESS_ID,
    render_tokens=True,
    support_profile=True,
)
