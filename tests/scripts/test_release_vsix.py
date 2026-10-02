# SPDX-License-Identifier: MIT

"""The release build packages the VS Code extension into ``dist/``.

The README's VS Code channel installs ``apothem.vsix`` from the GitHub
Release. Packaging it in the build job puts it in ``dist/``, so the existing
steps hash it into the provenance, sign it, attest it, and upload it with the
other assets. These checks keep that step in the job, ahead of the hashing,
and on the same ``vsce`` pin the Marketplace workflow uses.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _steps(workflow: str, job: str) -> list[dict[str, Any]]:
    data = yaml.safe_load((_WORKFLOWS / workflow).read_text(encoding="utf-8"))
    steps = data["jobs"][job]["steps"]
    assert isinstance(steps, list)
    return steps


def _vsce_pin(text: str) -> str:
    match = re.search(r"@vscode/vsce@(\d+\.\d+\.\d+)", text)
    assert match is not None
    return match.group(1)


def test_build_job_packages_the_extension_before_hashing() -> None:
    steps = _steps("release.yml", "build")
    names = [str(step.get("name", "")) for step in steps]
    package = names.index("Package the VS Code extension")
    assert package < names.index("Compute artifact hashes")
    step = steps[package]
    assert step["working-directory"] == "vscode-extension"
    assert "--out ../dist/apothem.vsix" in step["run"]


def test_node_setup_in_the_release_build_has_no_cache() -> None:
    for step in _steps("release.yml", "build"):
        if str(step.get("uses", "")).startswith("actions/setup-node@"):
            assert step["with"]["package-manager-cache"] is False
            return
    raise AssertionError("the release build sets up Node for vsce")


def test_vsce_pin_matches_the_marketplace_workflow() -> None:
    release = (_WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    marketplace = (_WORKFLOWS / "publish-vscode.yml").read_text(encoding="utf-8")
    assert _vsce_pin(release) == _vsce_pin(marketplace)
