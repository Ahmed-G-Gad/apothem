# SPDX-License-Identifier: MIT

"""Tests for SBOM generation release helpers."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Final

import pytest

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SH_SCRIPT: Final[Path] = REPO_ROOT / "scripts" / "release" / "generate-sbom.sh"
PS1_SCRIPT: Final[Path] = REPO_ROOT / "scripts" / "release" / "generate-sbom.ps1"


def test_generate_sbom_scripts_use_pyproject_version_source() -> None:
    sh_text = SH_SCRIPT.read_text(encoding="utf-8")
    ps1_text = PS1_SCRIPT.read_text(encoding="utf-8")

    assert "pyproject.toml" in sh_text
    assert "pyproject.toml" in ps1_text
    assert '"${REPO_ROOT}/VERSION"' not in sh_text
    assert "Join-Path $RepoRoot 'VERSION'" not in ps1_text


def test_generate_sbom_sh_runs_without_version_file(tmp_path: Path) -> None:
    bash = find_test_bash()
    if bash is None:
        pytest.skip(SKIP_REASON)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    syft = fake_bin / "syft"
    # The stub models syft's two roles in generate-sbom.sh: the repo dir-scan
    # (emits the apothem package) and the staged-requirements scan of the
    # vendored closure (emits the vendored packages so the script's merge +
    # vendored-package assertion pass). It keys on whether the scanned source
    # path contains a requirements.txt — the staged vendored-closure scan does.
    syft.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
out=""
src=""
for arg in "$@"; do
  case "$arg" in
    spdx-json=*) out="${arg#spdx-json=}" ;;
    dir:*) src="${arg#dir:}" ;;
  esac
done
if [[ -z "$out" ]]; then
  echo "missing spdx-json output argument" >&2
  exit 1
fi
if [[ -n "$src" && -f "$src/requirements.txt" ]]; then
  printf '{"spdxVersion":"SPDX-2.3","packages":[{"name":"attrs","versionInfo":"26.1.0"},{"name":"jsonschema","versionInfo":"4.26.0"},{"name":"jsonschema-specifications","versionInfo":"2025.9.1"},{"name":"referencing","versionInfo":"0.37.0"},{"name":"pyyaml","versionInfo":"6.0.3"},{"name":"typing-extensions","versionInfo":"4.15.0"},{"name":"rpds-py","versionInfo":"0.30.0"}]}\\n' > "$out"
else
  printf '{"spdxVersion":"SPDX-2.3","packages":[{"name":"apothem"}]}\\n' > "$out"
fi
""",
        encoding="utf-8",
    )
    syft.chmod(0o755)

    output = tmp_path / "sbom.spdx.json"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    completed = subprocess.run(
        [bash, str(SH_SCRIPT), str(output)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert output.is_file()
    # The script merges the vendored closure into the SBOM and re-serialises it
    # (pretty-printed JSON), so parse rather than substring-match on the raw bytes.
    sbom = json.loads(output.read_text(encoding="utf-8"))
    assert sbom["spdxVersion"] == "SPDX-2.3"
    # The vendored distributions are enumerated alongside the dir-scan packages.
    names = {pkg.get("name", "").lower() for pkg in sbom["packages"]}
    for vendored in (
        "attrs",
        "jsonschema",
        "referencing",
        "pyyaml",
        "typing-extensions",
    ):
        assert vendored in names, f"vendored package {vendored} absent from SBOM"
