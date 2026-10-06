# SPDX-License-Identifier: MIT

"""Central registry for supported Apothem harness adapters.

The declarative ``HARNESS_REGISTRY`` data table lives in the sibling
``harness_registry_data`` module; this module imports it and carries the
resolution / discovery logic plus the derived lookup indexes. It re-exports the
full public surface (data + types + functions) so
``from apothem.lib.harness_registry import X`` is unchanged for every consumer.
This module is authoritative at runtime.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

from apothem.lib.harness_protocol import HarnessAdapter
from apothem.lib.harness_registry_data import (
    CROSS_TOOL_INSTRUCTION_FILES as CROSS_TOOL_INSTRUCTION_FILES,
)
from apothem.lib.harness_registry_data import (
    HARNESS_REGISTRY as HARNESS_REGISTRY,
)
from apothem.lib.harness_registry_data import (
    PRIVATE_INSTRUCTION_TARGETS as PRIVATE_INSTRUCTION_TARGETS,
)
from apothem.lib.harness_registry_data import (
    REQUIRED_CAPABILITIES as REQUIRED_CAPABILITIES,
)
from apothem.lib.harness_registry_data import (
    SHARED_ROOTS as SHARED_ROOTS,
)
from apothem.lib.harness_registry_data import (
    SUPPORTED_HARNESS_COUNT as SUPPORTED_HARNESS_COUNT,
)
from apothem.lib.harness_registry_data import (
    CapabilityStatus as CapabilityStatus,
)
from apothem.lib.harness_registry_data import (
    HarnessRegistryEntry as HarnessRegistryEntry,
)
from apothem.lib.harness_registry_data import (
    HarnessScope as HarnessScope,
)
from apothem.lib.harness_registry_data import (
    SharedRoot as SharedRoot,
)

SUPPORTED_HARNESS_IDS: tuple[str, ...] = tuple(
    entry.public_id for entry in HARNESS_REGISTRY
)
SUPPORTED_PACKAGE_KEYS: tuple[str, ...] = tuple(
    entry.package_key for entry in HARNESS_REGISTRY
)

_BY_PUBLIC_ID: Mapping[str, HarnessRegistryEntry] = {
    entry.public_id: entry for entry in HARNESS_REGISTRY
}
_BY_PACKAGE_KEY: Mapping[str, HarnessRegistryEntry] = {
    entry.package_key: entry for entry in HARNESS_REGISTRY
}

if len(HARNESS_REGISTRY) != SUPPORTED_HARNESS_COUNT:  # pragma: no cover
    raise RuntimeError(
        "the supported harness registry must contain exactly "
        f"{SUPPORTED_HARNESS_COUNT} entries"
    )
if len(set(SUPPORTED_HARNESS_IDS)) != SUPPORTED_HARNESS_COUNT:  # pragma: no cover
    raise RuntimeError("duplicate public harness ids in registry")
if len(set(SUPPORTED_PACKAGE_KEYS)) != SUPPORTED_HARNESS_COUNT:  # pragma: no cover
    raise RuntimeError("duplicate harness package keys in registry")


def normalize_harness_reference(value: object) -> str:
    """Normalize a public id or package key reference for registry lookup."""
    return str(value).strip().lower()


def iter_harness_entries() -> tuple[HarnessRegistryEntry, ...]:
    """Return registry entries in their deterministic, source-declared order."""
    return HARNESS_REGISTRY


def get_harness_entry(value: object) -> HarnessRegistryEntry:
    """Return the registry entry addressed by public id or package key."""
    key = normalize_harness_reference(value)
    if key in _BY_PUBLIC_ID:
        return _BY_PUBLIC_ID[key]
    if key in _BY_PACKAGE_KEY:
        return _BY_PACKAGE_KEY[key]
    raise KeyError(key)


def public_id_for_package_key(package_key: object) -> str:
    """Return the public harness id for a Python package key."""
    return get_harness_entry(package_key).public_id


def package_key_for_public_id(public_id: object) -> str:
    """Return the Python package key for a public harness id."""
    return get_harness_entry(public_id).package_key


def load_adapter_class(entry: HarnessRegistryEntry) -> type[object]:
    """Import and return the adapter class declared by a registry entry."""
    module = importlib.import_module(entry.adapter_module)
    adapter_class = getattr(module, entry.adapter_class_name)
    if not isinstance(adapter_class, type):
        raise TypeError(f"{entry.entry_point} did not resolve to a class")
    return adapter_class


class AdapterDiscoveryError(RuntimeError):
    """Raised when a harness sub-package fails convention-based adapter resolution.

    The error message names the offending directory so a silently-dropped
    adapter never becomes an invisible coverage regression.
    """


# Directory names under ``harnesses/`` that hold shared helpers rather than a
# concrete adapter sub-package. They are skipped during discovery alongside
# private (underscore / dot prefixed) and cache directories.
_DISCOVERY_HELPER_DIRS: frozenset[str] = frozenset({"_shared", "templates"})


def _adapter_canonical_name(package_key: str) -> str:
    """Return the canonical kebab-case name for a harness package directory.

    Reuses the static registry's ``package_key`` -> ``public_id`` mapping for
    fidelity (e.g. ``claude_code`` -> ``claude-code``). Falls back to a direct
    underscore-to-hyphen transform when the directory is not yet registered,
    so a newly-added adapter is still discoverable before the static registry
    is updated.
    """
    entry = _BY_PACKAGE_KEY.get(package_key)
    if entry is not None:
        return entry.public_id
    return package_key.replace("_", "-")


def _resolve_adapter_class(package_key: str, module: object) -> type[object]:
    """Find the single ``*Adapter`` class exposed by an imported harness module.

    The class name is resolved by convention rather than computed from the
    directory name: the snake-to-Pascal transform is not reliable (for
    instance ``github_copilot`` exposes ``GitHubCopilotAdapter`` with an
    internal capital ``H``). Instead every attribute whose name ends with
    ``Adapter`` and is a class is collected; exactly one must be present.
    """
    candidates: list[type[object]] = []
    for attr_name in dir(module):
        if not attr_name.endswith("Adapter"):
            continue
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and attr is not HarnessAdapter:
            candidates.append(attr)

    # De-duplicate while preserving identity (an adapter may be re-exported
    # under more than one attribute name pointing at the same class object).
    unique = list(dict.fromkeys(candidates))
    if not unique:
        raise AdapterDiscoveryError(
            f"harnesses/{package_key}: no '*Adapter' class found in the package module"
        )
    if len(unique) > 1:
        names = ", ".join(sorted(cls.__name__ for cls in unique))
        raise AdapterDiscoveryError(
            f"harnesses/{package_key}: expected exactly one '*Adapter' class, "
            f"found {len(unique)} ({names})"
        )
    return unique[0]


def _is_installed_package_root(root: Path) -> bool:
    """Return ``True`` when ``root`` is the installed ``apothem`` package dir."""
    import apothem

    apothem_file = getattr(apothem, "__file__", None)
    if apothem_file is None:  # pragma: no cover - namespace package edge
        return False
    return Path(apothem_file).resolve().parent == root.resolve()


def _import_harness_module(root: Path, name: str, package_dir: Path) -> ModuleType:
    """Import the harness sub-package ``name`` found under ``root / harnesses``.

    When ``root`` is the installed ``apothem`` package directory the robust
    namespace import (``apothem.harnesses.<name>``) is used — this honors
    editable installs and namespace-package layouts. Otherwise the module is
    loaded directly from its ``__init__.py`` on disk, so an arbitrary ``root``
    (for instance a test fixture tree) is enumerated against the actual files
    it contains rather than the installed package.
    """
    if _is_installed_package_root(root):
        return importlib.import_module(f"apothem.harnesses.{name}")

    fq_name = f"_apothem_discovered_harness_{name}"
    spec = importlib.util.spec_from_file_location(fq_name, package_dir / "__init__.py")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise AdapterDiscoveryError(
            f"harnesses/{name}: package could not be loaded from {package_dir}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[fq_name] = module
    spec.loader.exec_module(module)
    return module


def discover_adapters(root: Path) -> dict[str, type[object]]:
    """Discover harness adapters by filesystem convention under ``root``.

    Conformance utility, NOT the runtime resolver. The authoritative
    adapter source at runtime is the static :data:`HARNESS_REGISTRY`; this
    discovery exists so a parity test can assert the on-disk adapter set
    equals the registry, catching a convention-correct but unregistered
    adapter as a coverage regression. No CLI / runtime path calls this.

    Scans the immediate subdirectories of ``root / "harnesses"``, importing
    each package and resolving its ``*Adapter`` class by convention. The
    returned mapping is keyed by the adapter's canonical kebab-case name and
    ordered deterministically (sorted by key).

    Args:
        root: The ``apothem`` package directory whose ``harnesses/``
            subdirectory holds the per-harness adapter sub-packages.

    Returns:
        A ``dict`` mapping canonical harness name (e.g. ``'claude-code'``)
        to the resolved adapter class, in sorted key order.

    Raises:
        AdapterDiscoveryError: When a candidate sub-package exposes zero or
            more than one ``*Adapter`` class. The message names the directory.
    """
    harnesses_dir = root / "harnesses"
    discovered: dict[str, type[object]] = {}
    for child in sorted(harnesses_dir.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith(("_", ".")) or name in _DISCOVERY_HELPER_DIRS:
            continue
        if not (child / "__init__.py").is_file():
            continue
        module = _import_harness_module(root, name, child)
        adapter_class = _resolve_adapter_class(name, module)
        discovered[_adapter_canonical_name(name)] = adapter_class
    return dict(sorted(discovered.items()))


def discovered_adapter_map() -> dict[str, type[object]]:
    """Discover adapters under the installed ``apothem`` package directory.

    Convenience wrapper over :func:`discover_adapters` that defaults ``root``
    to the directory of the installed ``apothem`` package, so callers need
    not compute it themselves. Like :func:`discover_adapters`, this is a
    conformance/parity utility (registry-vs-filesystem agreement), not the
    runtime adapter resolver — the static :data:`HARNESS_REGISTRY` is
    authoritative at runtime.

    Returns:
        A ``dict`` mapping canonical harness name to adapter class, sorted.
    """
    import apothem

    package_root = Path(apothem.__file__).resolve().parent
    return discover_adapters(package_root)


__all__ = [
    "CROSS_TOOL_INSTRUCTION_FILES",
    "HARNESS_REGISTRY",
    "PRIVATE_INSTRUCTION_TARGETS",
    "REQUIRED_CAPABILITIES",
    "SHARED_ROOTS",
    "SUPPORTED_HARNESS_COUNT",
    "SUPPORTED_HARNESS_IDS",
    "SUPPORTED_PACKAGE_KEYS",
    "AdapterDiscoveryError",
    "CapabilityStatus",
    "HarnessRegistryEntry",
    "HarnessScope",
    "SharedRoot",
    "discover_adapters",
    "discovered_adapter_map",
    "get_harness_entry",
    "iter_harness_entries",
    "load_adapter_class",
    "normalize_harness_reference",
    "package_key_for_public_id",
    "public_id_for_package_key",
]
