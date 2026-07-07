# SPDX-License-Identifier: MIT

"""Self-contained engine-import bootstrap for the bundled plugin tree.

Why this module exists. The plugin-first distribution ships the apothem
engine as a bundled copy under ``<plugin_root>/lib/apothem``: the bundled
plugin tree imports the engine and its vendored dependencies directly
from the tree, and no package installation occurs at any point. A harness
that loads the plugin needs ``import apothem`` (and the alias ``import
apothem_lib``) plus every vendored third-party dependency to resolve from
the plugin tree. This module mutates ``sys.path`` so those imports
succeed, and does so idempotently — calling it once per session boundary,
or twice by accident, leaves ``sys.path`` in the same correct state.

The self-containment invariant. Vendored dependencies under
``lib/apothem/_vendor`` take precedence over any system-installed copy.
``bootstrap_syspath`` prepends the vendor directory ahead of ``sys.path``
so the bundled versions win the import resolution race.

Public API. ``bootstrap_syspath`` performs the idempotent mutation;
``bootstrapped_root`` returns the last root bootstrapped for diagnostics;
``PluginBootstrapError`` is raised on a malformed plugin tree (missing
``plugin_root`` or missing ``lib/``) — failing loud rather than silently
importing a stale system copy.
"""

from __future__ import annotations

import sys
from pathlib import Path

__all__ = [
    "PluginBootstrapError",
    "bootstrap_syspath",
    "bootstrapped_root",
]


class PluginBootstrapError(RuntimeError):
    """Raised when the plugin tree is malformed and cannot be bootstrapped.

    The error message names the missing path so the operator can diagnose
    a malformed plugin without inspecting the bootstrap logic.
    """


# Module-level registry of already-bootstrapped roots. Membership here
# guards against duplicate sys.path entries on repeated calls; the
# resolved (absolute) path is the canonical key so two spellings of the
# same root collapse to one entry.
_BOOTSTRAPPED_ROOTS: set[Path] = set()

# Diagnostics handle: the last root passed to bootstrap_syspath.
_LAST_BOOTSTRAPPED_ROOT: Path | None = None


def bootstrap_syspath(plugin_root: Path) -> None:
    """Idempotently prepend the bundled engine to ``sys.path``.

    After this call, ``import apothem`` and ``import apothem_lib`` resolve
    from ``<plugin_root>/lib`` and any vendored third-party dependency
    resolves from ``<plugin_root>/lib/apothem/_vendor`` ahead of a
    system-installed copy — the plugin tree is self-contained.

    Pre-conditions:
        ``plugin_root`` exists and contains a ``lib/`` directory.

    Post-conditions:
        ``str(lib_dir)`` is present at ``sys.path[0]``. When the vendor
        directory exists, ``str(vendor_dir)`` is present at ``sys.path[0]``
        ahead of ``lib_dir`` (vendor precedence). Repeated calls add no
        duplicate entries.

    Args:
        plugin_root: The plugin tree root containing ``.claude-plugin/``
            and ``lib/``.

    Raises:
        PluginBootstrapError: If ``plugin_root`` does not exist, or if it
            has no ``lib/`` directory. The message names the missing path.
    """
    global _LAST_BOOTSTRAPPED_ROOT

    resolved_root = plugin_root.resolve()

    if not resolved_root.exists():
        raise PluginBootstrapError(f"plugin_root does not exist: {resolved_root}")

    lib_dir = resolved_root / "lib"
    if not lib_dir.is_dir():
        raise PluginBootstrapError(f"plugin_root has no lib/ directory: {lib_dir}")

    _LAST_BOOTSTRAPPED_ROOT = resolved_root

    # Idempotency short-circuit: a root already bootstrapped needs no
    # further sys.path mutation. The path-membership checks below are a
    # second line of defense against duplicates introduced out-of-band.
    if resolved_root in _BOOTSTRAPPED_ROOTS:
        return

    vendor_dir = lib_dir / "apothem" / "_vendor"

    # Prepend lib_dir first so it lands at sys.path[0]; the vendor
    # prepend below then displaces it to sys.path[1], yielding the
    # vendor-before-lib ordering the self-containment invariant requires.
    _prepend_unique(str(lib_dir))

    if vendor_dir.is_dir():
        _prepend_unique(str(vendor_dir))

    _BOOTSTRAPPED_ROOTS.add(resolved_root)


def bootstrapped_root() -> Path | None:
    """Return the last root passed to ``bootstrap_syspath``.

    Returns:
        The resolved path of the most recently bootstrapped plugin root,
        or ``None`` if ``bootstrap_syspath`` has not yet succeeded past
        its validation gate.
    """
    return _LAST_BOOTSTRAPPED_ROOT


def _prepend_unique(entry: str) -> None:
    """Prepend ``entry`` to ``sys.path[0]`` only if not already present.

    Args:
        entry: The ``sys.path`` entry to prepend.
    """
    if entry not in sys.path:
        sys.path.insert(0, entry)
