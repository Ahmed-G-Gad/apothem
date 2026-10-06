# SPDX-License-Identifier: MIT

"""Tests for the generate-sbom.{sh,ps1} release wrappers.

Both wrappers delegate to scripts/release/generate_sbom.py, the generator the
release workflow runs, so a locally built asset matrix carries the same SBOM
as a release: one describing the built distributions, not a scan of the
checkout. The generator itself is covered by test_generate_sbom_from_dist.py.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Final

import pytest

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SH_SCRIPT: Final[Path] = REPO_ROOT / "scripts" / "release" / "generate-sbom.sh"
PS1_SCRIPT: Final[Path] = REPO_ROOT / "scripts" / "release" / "generate-sbom.ps1"


def test_wrappers_delegate_to_the_release_generator() -> None:
    for script in (SH_SCRIPT, PS1_SCRIPT):
        text = script.read_text(encoding="utf-8")
        assert "generate_sbom.py" in text, script.name
        assert "syft" not in text, f"{script.name} still scans the checkout"
        assert "sbom.cdx.json" in text, script.name


def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    with zipfile.ZipFile(dist / "apothem-9.9.9-py3-none-any.whl", "w") as wheel:
        wheel.writestr(
            "apothem-9.9.9.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: apothem\nVersion: 9.9.9\n"
            "License-Expression: MIT\n",
        )
    with tarfile.open(dist / "apothem-9.9.9.tar.gz", "w:gz") as sdist:
        data = b"# no vendored packages in this fixture\n"
        info = tarfile.TarInfo("apothem-9.9.9/src/apothem/_vendor/vendor.txt")
        info.size = len(data)
        sdist.addfile(info, io.BytesIO(data))
    return dist


def test_generate_sbom_sh_writes_the_distribution_sbom(tmp_path: Path) -> None:
    bash = find_test_bash()
    if bash is None:
        pytest.skip(SKIP_REASON)
    output = tmp_path / "out" / "sbom.cdx.json"
    completed = subprocess.run(
        [bash, str(SH_SCRIPT), str(output), str(_dist(tmp_path))],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    sbom = json.loads(output.read_text(encoding="utf-8"))
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["metadata"]["component"]["purl"] == "pkg:pypi/apothem@9.9.9"


def test_generate_sbom_sh_fails_without_distributions(tmp_path: Path) -> None:
    bash = find_test_bash()
    if bash is None:
        pytest.skip(SKIP_REASON)
    empty = tmp_path / "empty"
    empty.mkdir()
    completed = subprocess.run(
        [bash, str(SH_SCRIPT), str(tmp_path / "sbom.cdx.json"), str(empty)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "expected one *.whl" in completed.stderr
