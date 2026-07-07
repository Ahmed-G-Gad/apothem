# SPDX-License-Identifier: MIT

"""Update logic for the trae harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_update_project
from apothem.harnesses.trae.install import install

update = make_update_project(install)
