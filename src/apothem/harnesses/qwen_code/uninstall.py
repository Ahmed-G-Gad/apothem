# SPDX-License-Identifier: MIT

"""Uninstall logic for the qwen-code harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_native_config_uninstall
from apothem.harnesses.qwen_code.materializer import materialize_native_config

_HARNESS_NAME: str = "qwen_code"

# The native ``settings.json`` is rendered by the materializer rather than the
# manifest, so it is cleaned surgically: only Apothem's keys (``context``, the
# hook handlers, the ``mcpServers`` block) are stripped from the parsed operator
# JSON — operator-added keys and non-Apothem hooks survive — and the file is
# deleted only when nothing operator-authored remains. The pre-mutation file is
# copied into the Apothem backup root; no whole-file ``.bak`` sibling is left
# beside the operator's file. The manifest support subtree is then cleaned
# child-by-child by the shared driver.
uninstall = make_native_config_uninstall(
    _HARNESS_NAME,
    materialize_native_config,
    apothem_keys=frozenset({"mcpServers"}),
)
