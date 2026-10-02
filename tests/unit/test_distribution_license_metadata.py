# SPDX-License-Identifier: MIT

"""The distribution's license metadata covers every license it ships.

PEP 639's ``License-Expression`` describes the whole distribution. The wheel
and sdist declared ``MIT`` while shipping ``apothem/_vendor/typing_extensions.py``
under PSF-2.0, so license scanners under-reported the obligations. The
expression and ``license-files`` now follow the licenses REUSE.toml records
for the vendored tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _vendored_license_ids() -> set[str]:
    tomllib = pytest.importorskip("tomllib")
    reuse = tomllib.loads((_REPO_ROOT / "REUSE.toml").read_text(encoding="utf-8"))
    ids: set[str] = set()
    for annotation in reuse["annotations"]:
        paths = annotation["path"]
        paths = [paths] if isinstance(paths, str) else paths
        if any(str(p).startswith("src/apothem/_vendor/") for p in paths):
            ids.add(annotation["SPDX-License-Identifier"])
    return ids


def _project() -> dict[str, object]:
    tomllib = pytest.importorskip("tomllib")
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return dict(data["project"])


def test_license_expression_covers_every_vendored_license() -> None:
    expression = str(_project()["license"])
    declared = set(re.findall(r"[A-Za-z0-9.+-]+", expression)) - {"AND", "OR", "WITH"}
    missing = _vendored_license_ids() - declared
    assert not missing, f"License-Expression {expression!r} omits {sorted(missing)}"


def test_every_declared_license_text_ships() -> None:
    expression = str(_project()["license"])
    files = _project()["license-files"]
    assert isinstance(files, list)
    for license_id in set(re.findall(r"[A-Za-z0-9.+-]+", expression)) - {"AND", "OR"}:
        rel = f"LICENSES/{license_id}.txt"
        assert rel in files, f"license-files omits {rel}"
        assert (_REPO_ROOT / rel).is_file(), f"{rel} does not exist"
