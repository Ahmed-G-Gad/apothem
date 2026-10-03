# SPDX-License-Identifier: MIT

"""The release packages the VS Code extension in a job of its own.

The README's VS Code channel installs ``apothem.vsix`` from the GitHub
Release, so the build job places it in ``dist/`` where the existing steps hash
it into the provenance, sign it, attest it, and upload it with the other
assets. The packager itself runs in a separate job: vsce installs from the
committed ``.github/vsce`` lockfile with ``npm ci --ignore-scripts``, never
where the Python distributions are built, and only ``apothem.vsix`` leaves
that job. The Marketplace workflow installs vsce the same way.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

_REPO = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO / ".github" / "workflows"
_VSCE = _REPO / ".github" / "vsce"
_LOCKED_INSTALL = "npm ci --prefix {prefix} --ignore-scripts"


def _job(workflow: str, job: str) -> dict[str, Any]:
    data = yaml.safe_load((_WORKFLOWS / workflow).read_text(encoding="utf-8"))
    found = data["jobs"][job]
    assert isinstance(found, dict)
    return found


def _runs(job: dict[str, Any]) -> list[str]:
    return [str(step["run"]) for step in job["steps"] if "run" in step]


def test_the_vsix_job_installs_vsce_from_the_lockfile_without_scripts() -> None:
    job = _job("release.yml", "vsix")
    runs = _runs(job)
    assert any(_LOCKED_INSTALL.format(prefix=".github/vsce") in run for run in runs)
    assert not any("npx" in run for run in runs)
    for step in job["steps"]:
        if str(step.get("uses", "")).startswith("actions/setup-node@"):
            assert step["with"]["package-manager-cache"] is False


def test_only_the_extension_leaves_the_vsix_job() -> None:
    uploads = [
        step
        for step in _job("release.yml", "vsix")["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert len(uploads) == 1
    assert uploads[0]["with"]["name"] == "vsix"
    assert str(uploads[0]["with"]["path"]).endswith("/apothem.vsix")


def test_the_build_job_adds_the_extension_to_dist_before_hashing() -> None:
    job = _job("release.yml", "build")
    assert "vsix" in job["needs"]
    names = [str(step.get("name", "")) for step in job["steps"]]
    add = names.index("Add the VS Code extension to dist/")
    assert add < names.index("Compute artifact hashes")
    step = job["steps"][add]
    assert str(step["uses"]).startswith("actions/download-artifact@")
    assert step["with"] == {"name": "vsix", "path": "dist/"}


def test_the_build_job_runs_no_node_tooling() -> None:
    job = _job("release.yml", "build")
    assert not any(
        str(step.get("uses", "")).startswith("actions/setup-node@")
        for step in job["steps"]
    )
    for run in _runs(job):
        assert "npx" not in run
        assert "npm " not in run


def test_the_marketplace_workflow_uses_the_same_lockfile() -> None:
    runs = _runs(_job("publish-vscode.yml", "publish"))
    assert any(_LOCKED_INSTALL.format(prefix="../.github/vsce") in run for run in runs)
    assert not any("npx" in run for run in runs)


def test_the_lockfile_pins_vsce_and_every_dependency_by_hash() -> None:
    manifest = json.loads((_VSCE / "package.json").read_text(encoding="utf-8"))
    pin = manifest["dependencies"]["@vscode/vsce"]
    assert pin[0].isdigit(), "an exact version, not a range"
    lock = json.loads((_VSCE / "package-lock.json").read_text(encoding="utf-8"))
    packages = lock["packages"]
    assert packages["node_modules/@vscode/vsce"]["version"] == pin
    unhashed = [
        name for name, entry in packages.items() if name and "integrity" not in entry
    ]
    assert unhashed == []
