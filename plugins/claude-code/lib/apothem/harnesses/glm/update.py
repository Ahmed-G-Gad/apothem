# SPDX-License-Identifier: MIT

"""Update logic for the glm harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_update_project
from apothem.harnesses.glm.install import install

update = make_update_project(install)
