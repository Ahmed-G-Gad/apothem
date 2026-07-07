# SPDX-License-Identifier: MIT

"""Update logic for the antigravity harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_update
from apothem.harnesses.antigravity.install import install

update = make_update(install)
