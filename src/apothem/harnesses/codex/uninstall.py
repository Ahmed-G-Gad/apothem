# SPDX-License-Identifier: MIT

"""Uninstall logic for the codex harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_uninstall

# AGENTS.md is a ``sentinel_merge`` anchor and hooks.json an operator-owned
# ``write_text`` JSON target, so the shared driver strips only Apothem's managed
# block / keys / hook handlers (operator prose and operator keys survive) and
# backs each file up under the Apothem backup root — no whole-file ``.bak``
# sibling is left beside the operator's files.
_HARNESS_NAME: str = "codex"

uninstall = make_uninstall(_HARNESS_NAME)
