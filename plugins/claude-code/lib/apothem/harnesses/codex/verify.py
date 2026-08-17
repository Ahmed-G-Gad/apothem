# SPDX-License-Identifier: MIT

"""Verify logic for the codex harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_verify_harness_root

_HARNESS_NAME: str = "codex"

verify = make_verify_harness_root(_HARNESS_NAME)
