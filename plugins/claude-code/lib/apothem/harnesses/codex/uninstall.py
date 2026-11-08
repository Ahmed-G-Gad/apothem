# SPDX-License-Identifier: MIT

"""Uninstall logic for the codex harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared import install_driver_pathsafety
from apothem.harnesses._shared.wrapper_factories import make_uninstall

# AGENTS.md is a ``sentinel_merge`` anchor and hooks.json an operator-owned
# ``write_text`` JSON target, so the shared driver strips only Apothem's managed
# block / keys / hook handlers (operator prose and operator keys survive) and
# backs each file up under the Apothem backup root — no whole-file ``.bak``
# sibling is left beside the operator's files.
_HARNESS_NAME: str = "codex"

_uninstall = make_uninstall(_HARNESS_NAME)


def uninstall(output_path: Path) -> None:
    """Remove the Codex install at *output_path*'s folder.

    Refused, before anything is removed, when ``CODEX_HOME`` is spelled
    inside the home and a link leads it out (see
    :func:`~apothem.harnesses._shared.install_driver_pathsafety.refuse_link_leaving_home`).
    """
    install_driver_pathsafety.refuse_link_leaving_home(
        _HARNESS_NAME, output_path.parent, operation="codex_home", uninstall=True
    )
    _uninstall(output_path)
