# SPDX-License-Identifier: MIT

"""Verify logic for the qwen-code harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_verify_native_config

_HARNESS_NAME: str = "qwen_code"

verify = make_verify_native_config(_HARNESS_NAME)
