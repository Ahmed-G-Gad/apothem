# SPDX-License-Identifier: MIT

"""Unit tests for the self-contained engine-import bootstrap.

Each test builds a minimal fake plugin tree under ``tmp_path`` and asserts
``bootstrap_syspath`` mutates ``sys.path`` correctly. The ``isolate_syspath``
fixture saves and restores ``sys.path`` plus the module-level bootstrap
registry around every test so a mutation cannot leak into sibling tests
running in the same process.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from apothem.lib import plugin_bootstrap
from apothem.lib.plugin_bootstrap import (
    PluginBootstrapError,
    bootstrap_syspath,
    bootstrapped_root,
)


@pytest.fixture
def isolate_syspath() -> Iterator[None]:
    """Save and restore ``sys.path`` and the bootstrap registry per test."""
    saved_path = list(sys.path)
    saved_roots = set(plugin_bootstrap._BOOTSTRAPPED_ROOTS)
    saved_last = plugin_bootstrap._LAST_BOOTSTRAPPED_ROOT
    try:
        yield
    finally:
        sys.path[:] = saved_path
        plugin_bootstrap._BOOTSTRAPPED_ROOTS = saved_roots
        plugin_bootstrap._LAST_BOOTSTRAPPED_ROOT = saved_last


def _make_plugin_tree(root: Path, *, with_vendor: bool = True) -> Path:
    """Build a minimal fake plugin tree and return its root.

    Args:
        root: The directory under which the plugin tree is created.
        with_vendor: When True, create the ``lib/apothem/_vendor`` dir.

    Returns:
        The plugin-tree root (``root`` itself).
    """
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").touch()
    if with_vendor:
        (root / "lib" / "apothem" / "_vendor").mkdir(parents=True)
    else:
        (root / "lib" / "apothem").mkdir(parents=True)
    return root


def test_bootstrap_prepends_lib_and_vendor(
    tmp_path: Path, isolate_syspath: None
) -> None:
    plugin_root = _make_plugin_tree(tmp_path / "plugin", with_vendor=True)

    bootstrap_syspath(plugin_root)

    lib_dir = str((plugin_root / "lib").resolve())
    vendor_dir = str((plugin_root / "lib" / "apothem" / "_vendor").resolve())

    assert lib_dir in sys.path
    assert vendor_dir in sys.path
    # Vendor precedence: vendor_dir resolves before lib_dir.
    assert sys.path.index(vendor_dir) < sys.path.index(lib_dir)
    # lib_dir landed at the front before vendor displaced it.
    assert sys.path[0] == vendor_dir


def test_bootstrap_is_idempotent(tmp_path: Path, isolate_syspath: None) -> None:
    plugin_root = _make_plugin_tree(tmp_path / "plugin", with_vendor=True)

    bootstrap_syspath(plugin_root)
    path_after_first = list(sys.path)
    bootstrap_syspath(plugin_root)
    path_after_second = list(sys.path)

    assert path_after_first == path_after_second

    lib_dir = str((plugin_root / "lib").resolve())
    vendor_dir = str((plugin_root / "lib" / "apothem" / "_vendor").resolve())
    assert sys.path.count(lib_dir) == 1
    assert sys.path.count(vendor_dir) == 1


def test_bootstrap_without_vendor_adds_only_lib(
    tmp_path: Path, isolate_syspath: None
) -> None:
    plugin_root = _make_plugin_tree(tmp_path / "plugin", with_vendor=False)

    bootstrap_syspath(plugin_root)

    lib_dir = str((plugin_root / "lib").resolve())
    vendor_dir = str((plugin_root / "lib" / "apothem" / "_vendor").resolve())

    assert lib_dir in sys.path
    assert vendor_dir not in sys.path
    assert sys.path[0] == lib_dir


def test_bootstrap_missing_plugin_root_raises(
    tmp_path: Path, isolate_syspath: None
) -> None:
    missing = tmp_path / "does-not-exist"

    with pytest.raises(PluginBootstrapError) as excinfo:
        bootstrap_syspath(missing)

    assert str(missing.resolve()) in str(excinfo.value)


def test_bootstrap_missing_lib_dir_raises(
    tmp_path: Path, isolate_syspath: None
) -> None:
    plugin_root = tmp_path / "plugin"
    (plugin_root / ".claude-plugin").mkdir(parents=True)
    (plugin_root / ".claude-plugin" / "plugin.json").touch()
    # No lib/ directory created — malformed plugin.

    with pytest.raises(PluginBootstrapError) as excinfo:
        bootstrap_syspath(plugin_root)

    expected_lib = str((plugin_root / "lib").resolve())
    assert expected_lib in str(excinfo.value)


def test_bootstrapped_root_tracks_last_root(
    tmp_path: Path, isolate_syspath: None
) -> None:
    plugin_root = _make_plugin_tree(tmp_path / "plugin", with_vendor=True)

    bootstrap_syspath(plugin_root)

    assert bootstrapped_root() == plugin_root.resolve()
