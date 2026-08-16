# SPDX-License-Identifier: MIT

"""Apothem harness adapter protocol — the foundation contract.

Defines :class:`HarnessAdapter`, the structural contract every concrete
adapter must satisfy. It lives in the foundation ``lib`` layer so the harness
registry can reference the contract without the foundation importing its
consumers; :mod:`apothem.harnesses` re-exports it as the public surface
(importable as ``apothem.harnesses.HarnessAdapter``), and the adapters that
satisfy it are declared in :mod:`apothem.lib.harness_registry`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class HarnessAdapter(Protocol):
    """Protocol every apothem harness adapter must satisfy.

    Adapters translate a shared :class:`dict` profile into a
    harness-native configuration on disk.  The lifecycle contract is small:
    an adapter owns one primary ``output_path`` anchor, implements the
    install/update/uninstall/verify methods, and keeps the richer identity,
    target, docs, capability, and package-data obligations in the central
    registry.
    """

    @property
    def name(self) -> str:
        """Canonical kebab-case harness identifier (e.g. ``'claude-code'``)."""
        ...

    @property
    def output_path(self) -> Path:
        """Absolute path to the target configuration file."""
        ...

    def install(self, profile: dict[str, Any]) -> object:
        """Materialize the harness configuration from the shared profile dict."""
        ...

    def update(self, profile: dict[str, Any]) -> object:
        """Re-materialize the harness configuration from the updated profile."""
        ...

    def uninstall(self) -> None:
        """Remove the harness configuration file if present."""
        ...

    def is_installed(self) -> bool:
        """Return ``True`` if the harness configuration file exists on disk."""
        ...

    def verify(self) -> bool:
        """Return ``True`` if the installed harness configuration is valid."""
        ...
