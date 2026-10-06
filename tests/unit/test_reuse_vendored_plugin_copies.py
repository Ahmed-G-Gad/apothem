# SPDX-License-Identifier: MIT

"""REUSE.toml attributes the plugin tree's vendored copies like the originals.

The assembler copies the engine, ``_vendor`` included, into
``plugins/claude-code/lib/apothem/``. REUSE.toml annotated only
``src/apothem/_vendor/**``, so the shipped copies fell through to the
repository-wide baseline: PyYAML, jsonschema, attrs and referencing were
attributed to the maintainer, and typing_extensions was declared MIT instead
of PSF-2.0. ``reuse lint`` still passed, because every file had *some*
annotation. This test requires every vendored annotation path to name its
plugin-tree mirror in the same table.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.lib import plugin_tree

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_PREFIX = "src/apothem/"
_MIRROR_PREFIX = f"plugins/claude-code/{plugin_tree._ASSEMBLED_ENGINE_ROOT_REL}/"


def _annotations() -> list[dict[str, object]]:
    tomllib = pytest.importorskip("tomllib")
    data = tomllib.loads((_REPO_ROOT / "REUSE.toml").read_text(encoding="utf-8"))
    return list(data["annotations"])


def _paths(annotation: dict[str, object]) -> list[str]:
    paths = annotation["path"]
    return [paths] if isinstance(paths, str) else [str(p) for p in paths]  # type: ignore[union-attr]


def test_every_vendored_path_names_its_plugin_mirror() -> None:
    missing: list[str] = []
    for annotation in _annotations():
        paths = _paths(annotation)
        for path in paths:
            if not path.startswith(f"{_SRC_PREFIX}_vendor/"):
                continue
            mirror = _MIRROR_PREFIX + path[len(_SRC_PREFIX) :]
            if mirror not in paths:
                missing.append(f"{path} -> {mirror}")
    assert not missing, "vendored annotations lack plugin-tree mirrors:\n" + "\n".join(
        missing
    )


def test_vendored_tables_come_after_any_plugin_tree_table() -> None:
    """Last matching table wins, so the vendored tables must stay last."""
    tables = _annotations()
    vendored = [
        i
        for i, t in enumerate(tables)
        if any(p.startswith(f"{_MIRROR_PREFIX}_vendor/") for p in _paths(t))
    ]
    assert vendored, "no table annotates the plugin tree's vendored copies"
    broader = [
        i
        for i, t in enumerate(tables)
        if any(p in {"**", "plugins/**", "plugins/claude-code/**"} for p in _paths(t))
    ]
    assert max(broader) < min(vendored)
