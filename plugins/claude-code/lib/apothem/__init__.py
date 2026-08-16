# SPDX-License-Identifier: MIT

"""Apothem — host-agnostic AI harness configuration manager."""

from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path

#: How many ancestor directories to inspect for the source tree's manifest.
#: ``src/apothem/__init__.py`` sits two levels below the tree root, so three
#: levels covers the repository checkout, the npm package tree, and one
#: nesting layer of slack without ever walking into unrelated projects.
_MANIFEST_SEARCH_DEPTH = 3


def _version_from_source_tree() -> str | None:
    """Read the version from the ``pyproject.toml`` co-located with this tree.

    The self-contained runtime ships its source tree (a repository checkout,
    the npm package, or an installer-managed copy) without installed package
    metadata, so the co-located manifest is the authoritative version source.
    The manifest is accepted only when it declares ``name = "apothem"`` so a
    foreign ``pyproject.toml`` higher up the filesystem is never captured.

    Returns:
        The declared version, or ``None`` when no apothem manifest is found
        within the bounded ancestor walk.
    """
    for parent in Path(__file__).resolve().parents[:_MANIFEST_SEARCH_DEPTH]:
        candidate = parent / "pyproject.toml"
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            return None
        if re.search(r'^\s*name\s*=\s*["\']apothem["\']', text, flags=re.MULTILINE):
            match = re.search(
                r'^\s*version\s*=\s*["\']([^"\']+)["\']', text, flags=re.MULTILINE
            )
            return match.group(1) if match else None
        return None
    return None


def _resolve_version() -> str:
    """Resolve the package version: source tree first, then installed metadata.

    Precedence: the co-located ``pyproject.toml`` (the self-contained runtime's
    single source of truth, also authoritative for editable checkouts where
    stale installed metadata can shadow the tree), then ``importlib.metadata``
    for wheel installs, then the explicit unknown sentinel.
    """
    declared = _version_from_source_tree()
    if declared is not None:
        return declared
    try:
        return importlib.metadata.version(__name__)
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0+unknown"


__version__ = _resolve_version()
__author__ = "Ahmed G. Gad"
