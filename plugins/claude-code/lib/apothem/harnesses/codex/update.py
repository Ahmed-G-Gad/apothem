# SPDX-License-Identifier: MIT

"""Update logic for the codex harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_update
from apothem.harnesses.codex.install import install

update = make_update(install)
