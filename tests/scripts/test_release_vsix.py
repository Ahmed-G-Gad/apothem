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
    job = _job("publish-vscode.yml", "publish")
    runs = _runs(job)
    prefix = "../vsce-tool/.github/vsce"
    assert any(_LOCKED_INSTALL.format(prefix=prefix) in run for run in runs)
    # The lockfile comes from the workflow's own commit, not the tag being
    # packaged, so a dispatch for a tag cut before .github/vsce still works.
    tool = [
        step["with"]
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
        and step.get("with", {}).get("path") == "vsce-tool"
    ]
    assert tool == [
        {
            "persist-credentials": False,
            "ref": "${{ github.sha }}",
            "path": "vsce-tool",
            "sparse-checkout": ".github/vsce",
        }
    ]
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


def _vsce_jobs() -> list[dict[str, Any]]:
    """Return every release or Marketplace job that runs the vsce packager."""
    jobs = []
    for workflow in ("release.yml", "publish-vscode.yml"):
        data = yaml.safe_load((_WORKFLOWS / workflow).read_text(encoding="utf-8"))
        for job in data["jobs"].values():
            if "steps" in job and any("/.bin/vsce " in run for run in _runs(job)):
                jobs.append(job)
    return jobs


def test_every_vsce_run_packages_or_publishes_without_dependencies() -> None:
    # The vsix carries only vscode-extension/; --no-dependencies keeps vsce
    # from walking an npm tree into the package.
    # verify-pat only calls the Marketplace roles API; it neither packages nor
    # publishes, and it rejects the flag, so it is the one exemption.
    runs = [
        line
        for job in _vsce_jobs()
        for run in _runs(job)
        for line in run.splitlines()
        if "/.bin/vsce " in line and " verify-pat " not in line
    ]
    assert len(runs) >= 3, runs
    for line in runs:
        assert "--no-dependencies" in line, line


def test_each_vsce_job_sets_up_a_node_the_locked_vsce_supports() -> None:
    lock = json.loads((_VSCE / "package-lock.json").read_text(encoding="utf-8"))
    engines = lock["packages"]["node_modules/@vscode/vsce"]["engines"]["node"]
    floor = int(engines.lstrip(">= ").split(".")[0])
    jobs = _vsce_jobs()
    assert len(jobs) >= 2
    for job in jobs:
        versions = [
            str(step["with"]["node-version"])
            for step in job["steps"]
            if str(step.get("uses", "")).startswith("actions/setup-node@")
        ]
        assert versions, "a vsce job sets up Node explicitly"
        assert all(int(version.split(".")[0]) >= floor for version in versions)


_AZURE_LOGIN_SHA = "a641126d1b8aa4d1fa005f4f92df94a3a4c4c906"


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    found = [step for step in job["steps"] if step.get("name") == name]
    assert len(found) == 1, name
    return found[0]


def test_the_marketplace_job_can_request_an_oidc_token_for_entra_id() -> None:
    # A job-level permissions block replaces the workflow-level one, so the job
    # repeats contents: read next to id-token: write.
    job = _job("publish-vscode.yml", "publish")
    assert job["permissions"] == {"contents": "read", "id-token": "write"}


def test_the_entra_sign_in_is_pinned_to_a_commit_and_needs_no_subscription() -> None:
    job = _job("publish-vscode.yml", "publish")
    login = _step(job, "Sign in to Microsoft Entra ID")
    assert login["uses"] == f"Azure/login@{_AZURE_LOGIN_SHA}"
    assert login["with"]["allow-no-subscriptions"] is True
    assert "client-secret" not in login["with"]
    assert login["if"] == "${{ steps.auth.outputs.mode == 'entra' }}"


def test_the_entra_publish_step_uses_the_azure_credential_and_never_a_pat() -> None:
    # vsce prefers VSCE_PAT over --azure-credential, so an exported token would
    # silently turn the Entra publish into a PAT publish. AZURE_CLIENT_ID stays
    # out as well, which keeps the environment credential from being tried
    # before the Azure CLI session that Azure/login opened.
    job = _job("publish-vscode.yml", "publish")
    entra = _step(job, "Publish to Visual Studio Marketplace (Entra ID)")
    assert "--azure-credential" in entra["run"]
    assert "--no-dependencies" in entra["run"]
    assert "--pat" not in entra["run"]
    env = entra.get("env", {})
    assert "VSCE_PAT" not in env
    assert "AZURE_CLIENT_ID" not in env
    assert "mode == 'entra'" in entra["if"]
    assert "!inputs.dry_run" in entra["if"]


def test_the_pat_fallback_is_the_only_step_that_receives_the_token() -> None:
    job = _job("publish-vscode.yml", "publish")
    holders = [
        str(step["name"]) for step in job["steps"] if "VSCE_PAT" in step.get("env", {})
    ]
    assert holders == [
        "Select Marketplace credential",
        "Publish to Visual Studio Marketplace (PAT fallback)",
    ]
    fallback = _step(job, "Publish to Visual Studio Marketplace (PAT fallback)")
    assert "--azure-credential" not in fallback["run"]
    assert "mode == 'pat'" in fallback["if"]


def test_the_dry_run_input_publishes_nothing() -> None:
    data = yaml.safe_load(
        (_WORKFLOWS / "publish-vscode.yml").read_text(encoding="utf-8")
    )
    # PyYAML reads the bare `on` key as the boolean True.
    inputs = data[True]["workflow_dispatch"]["inputs"]
    assert inputs["dry_run"]["type"] == "boolean"
    assert inputs["dry_run"]["default"] is False
    job = data["jobs"]["publish"]
    for step in job["steps"]:
        name = str(step["name"])
        if name.startswith("Publish to Visual Studio Marketplace"):
            assert "!inputs.dry_run" in step["if"], name
        if name.startswith("Dry run"):
            assert "inputs.dry_run" in step["if"], name
            assert "!inputs.dry_run" not in step["if"], name
