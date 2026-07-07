# SPDX-License-Identifier: MIT

"""Unit tests for plugin-tree manifest version resolution.

_resolve_version's precedence is explicit-arg -> repo pyproject -> installed
``apothem.__version__``. The main suite resolves through the real pyproject;
these target the explicit-argument short-circuit and the final __version__
fallback branch when no pyproject version is discoverable.
"""

from __future__ import annotations

import pytest

from apothem.lib import plugin_tree as pt


def test_resolve_version_prefers_explicit_argument() -> None:
    assert pt._resolve_version("9.9.9") == "9.9.9"


def test_resolve_version_falls_back_to_installed_dunder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With no pyproject version discoverable, the installed __version__ is the
    # last-resort source.
    monkeypatch.setattr(pt, "_version_from_pyproject", lambda: None)
    from apothem import __version__

    assert pt._resolve_version(None) == __version__
