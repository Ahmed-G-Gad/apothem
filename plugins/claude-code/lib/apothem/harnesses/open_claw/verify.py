# SPDX-License-Identifier: MIT

"""Verify logic for the open-claw harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_verify_native_config

_HARNESS_NAME: str = "open_claw"

verify = make_verify_native_config(_HARNESS_NAME)
