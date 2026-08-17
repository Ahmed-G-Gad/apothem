# SPDX-License-Identifier: MIT

"""Verify logic for the zed harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_verify_project

_HARNESS_NAME: str = "zed"

verify = make_verify_project(_HARNESS_NAME)
