# SPDX-License-Identifier: MIT

"""Update logic for the qwen-code harness adapter."""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_update
from apothem.harnesses.qwen_code.install import install

update = make_update(install)
