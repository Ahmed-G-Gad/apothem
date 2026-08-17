# SPDX-License-Identifier: MIT

"""Verify logic for the claude-code harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_verify_harness_root

_HARNESS_NAME: str = "claude_code"

verify = make_verify_harness_root(_HARNESS_NAME)
