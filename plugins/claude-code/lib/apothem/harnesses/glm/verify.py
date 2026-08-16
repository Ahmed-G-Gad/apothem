# SPDX-License-Identifier: MIT

"""Verify logic for the glm harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_verify_project

_HARNESS_NAME: str = "glm"

verify = make_verify_project(_HARNESS_NAME)
