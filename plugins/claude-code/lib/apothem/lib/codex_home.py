# SPDX-License-Identifier: MIT

"""The Codex home folder: ``$CODEX_HOME``, else ``<home>/.codex``.

Codex keeps its ``AGENTS.md``, agents, hooks and configuration in one folder,
which the ``CODEX_HOME`` environment variable moves. The Codex adapter writes
there and the install advisories look there, so both resolve it with
:func:`codex_home`. The conformity gate keeps its own copy of the lookup: it
also runs from an installed support folder, without the engine to import.
"""

from __future__ import annotations

import os
from pathlib import Path


def codex_home(home: Path) -> Path:
    """Return the Codex home for a user whose home folder is *home*."""
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else home / ".codex"
