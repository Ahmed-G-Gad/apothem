# SPDX-License-Identifier: MIT

"""Uninstall logic for the antigravity harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_uninstall

# The GEMINI.md anchor is a ``sentinel_merge`` manifest target, so the shared
# driver strips only Apothem's managed block (operator prose survives) and backs
# the file up under the Apothem backup root — no whole-file ``.bak`` sibling is
# left beside the operator's file.
_HARNESS_NAME: str = "antigravity"

uninstall = make_uninstall(_HARNESS_NAME)
