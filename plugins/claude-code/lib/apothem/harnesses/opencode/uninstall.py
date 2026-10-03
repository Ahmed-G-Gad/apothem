# SPDX-License-Identifier: MIT

"""Uninstall logic for the opencode harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_native_config_uninstall
from apothem.harnesses.opencode.materializer import materialize_native_config

_HARNESS_NAME: str = "opencode"

# The native ``opencode.json`` is rendered by the materializer rather than the
# manifest, so it is cleaned surgically: only the entries the install ledger
# records as Apothem's (``$schema`` and ``instructions`` when Apothem added
# them, the MCP servers it wrote) are stripped from the parsed operator JSON —
# operator keys, operator MCP servers and operator ``instructions`` entries
# survive — and the file is deleted only when Apothem created it and nothing
# operator-authored remains. The pre-mutation file is copied into the Apothem
# backup root; no whole-file ``.bak`` sibling is left beside the operator's
# file. The manifest support subtree is then cleaned child-by-child by the
# shared driver.
uninstall = make_native_config_uninstall(_HARNESS_NAME, materialize_native_config)
