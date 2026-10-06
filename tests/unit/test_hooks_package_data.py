# SPDX-License-Identifier: MIT

"""The wheel ships the whole hook package, not just its Python modules.

The npm package, the plugin tree and the source checkout all carry
``hooks/hooks.json`` and the hook READMEs; the wheel and sdist left them out,
so a Python-channel install had a different hook corpus from every other
channel. This pins ``[tool.setuptools.package-data]`` to the package's actual
non-Python files.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_HOOKS = _REPO / "src" / "apothem" / "hooks"


def test_every_non_python_hook_file_is_package_data() -> None:
    # tomllib is stdlib from Python 3.11; the 3.10 floor skips the parse.
    tomllib = pytest.importorskip("tomllib")
    config = tomllib.loads((_REPO / "pyproject.toml").read_text(encoding="utf-8"))
    globs = config["tool"]["setuptools"]["package-data"]["apothem.hooks"]
    missing = [
        rel
        for path in sorted(_HOOKS.rglob("*"))
        if path.is_file()
        and path.suffix not in {".py", ".pyc"}
        and "__pycache__" not in path.parts
        for rel in [path.relative_to(_HOOKS).as_posix()]
        if not any(fnmatch.fnmatchcase(rel, pattern) for pattern in globs)
    ]
    assert not missing, f"hook files absent from the wheel: {missing}"
