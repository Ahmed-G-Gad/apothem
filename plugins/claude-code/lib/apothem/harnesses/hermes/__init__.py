# SPDX-License-Identifier: MIT

"""Apothem harness adapter for hermes.

Materializes ``~/.hermes/config.yaml`` from the shared profile: the Hermes
Agent user-global configuration file per the vendor canonical schema at
https://hermes-agent.nousresearch.com/docs/. The adapter-local
``STANDARD-CONVENTION-PIN.md`` records the current convention snapshot.
Delegates install logic to :mod:`apothem.harnesses.hermes.install`, which
renders the native config via :mod:`apothem.harnesses.hermes.materializer`.
"""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_native_config_adapter
from apothem.harnesses.hermes.install import install as _install
from apothem.harnesses.hermes.materializer import (
    materialize_native_config as materialize_native_config,
)
from apothem.harnesses.hermes.uninstall import uninstall as _uninstall
from apothem.harnesses.hermes.update import update as _update
from apothem.harnesses.hermes.verify import verify as _verify

HermesAdapter = make_native_config_adapter(
    "hermes",
    target_factory=lambda: Path.home() / ".hermes/config.yaml",
    install_fn=_install,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="HermesAdapter",
)
