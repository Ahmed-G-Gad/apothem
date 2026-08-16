# SPDX-License-Identifier: MIT

"""Update logic for the open-claw harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_update
from apothem.harnesses.open_claw.install import install

update = make_update(install)
