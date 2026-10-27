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
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
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


_SELECT = "Select Marketplace credential"


def _workflow(workflow: str) -> dict[str, Any]:
    data = yaml.safe_load((_WORKFLOWS / workflow).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


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
    # The shape, not the value: Dependabot's github-actions updates move the
    # commit, and the unpinned-action validator holds the version comment.
    assert re.fullmatch(r"Azure/login@[0-9a-f]{40}", str(login["uses"]))
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
    # A variable set on the job or the workflow reaches every step in it, the
    # Entra publish included, so neither level may carry either name.
    for scope in (_workflow("publish-vscode.yml"), job):
        assert "VSCE_PAT" not in scope.get("env", {})
        assert "AZURE_CLIENT_ID" not in scope.get("env", {})
    assert "mode == 'entra'" in entra["if"]
    assert "!inputs.dry_run" in entra["if"]


def test_the_pat_fallback_is_the_only_step_that_receives_the_token() -> None:
    job = _job("publish-vscode.yml", "publish")
    holders = [
        str(step["name"]) for step in job["steps"] if "VSCE_PAT" in step.get("env", {})
    ]
    assert holders == [
        _SELECT,
        "Publish to Visual Studio Marketplace (PAT fallback)",
    ]
    # Job-level or workflow-level env would hand the token to every step.
    assert "VSCE_PAT" not in _workflow("publish-vscode.yml").get("env", {})
    assert "VSCE_PAT" not in job.get("env", {})
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


def test_a_pat_dry_run_says_that_it_verified_nothing() -> None:
    # Only the Entra route has dry-run steps. On the PAT route a dry run would
    # otherwise be a green run that verified nothing.
    job = _job("publish-vscode.yml", "publish")
    notice = _step(job, "Dry run - the PAT route has no dry run")
    assert notice["if"] == "${{ steps.auth.outputs.mode == 'pat' && inputs.dry_run }}"
    assert "::warning" in notice["run"]


def test_the_skip_notice_runs_only_when_no_credential_is_configured() -> None:
    job = _job("publish-vscode.yml", "publish")
    notice = _step(job, "Marketplace publish skipped (not yet enabled)")
    assert notice["if"] == "${{ steps.auth.outputs.mode == 'none' }}"


def _bash_runs_the_selector() -> str | None:
    """Return a bash that can run the step and write ``$GITHUB_OUTPUT``, if any.

    On Windows ``bash`` can be the WSL launcher, which cannot open a Windows
    path, so the probe writes through the same variable the step uses.
    """
    bash = shutil.which("bash")
    if bash is None:
        return None
    with tempfile.TemporaryDirectory() as scratch:
        probe = Path(scratch) / "github-output"
        try:
            subprocess.run(
                [bash, "-c", 'echo ok >> "$GITHUB_OUTPUT"'],
                env={**os.environ, "GITHUB_OUTPUT": probe.as_posix()},
                capture_output=True,
                timeout=60,
                check=False,
            )
            ok = probe.read_text(encoding="utf-8").strip() == "ok"
        except (OSError, subprocess.SubprocessError):
            return None
    return bash if ok else None


_SELECTOR_BASH = _bash_runs_the_selector()
_TOKEN = "pat-value-that-must-never-be-printed"  # noqa: S105  # nosec B105 - a fixture value
_IDS = {"AZURE_CLIENT_ID": "client", "AZURE_TENANT_ID": "tenant"}
_ENTRA = {"VSCE_AUTH": "entra", **_IDS}
_PAT = {"VSCE_PAT": _TOKEN}
_READY = {"MARKETPLACE_READY": "true"}
_INCOMPLETE = "Entra variables incomplete"

# (id, environment, expected mode, expect the incomplete-Entra warning)
_SELECTOR_CASES = [
    ("not-ready-entra", {**_ENTRA}, "none", False),
    ("not-ready-pat", {**_PAT}, "none", False),
    ("ready-false", {"MARKETPLACE_READY": "false", **_ENTRA, **_PAT}, "none", False),
    ("ready-no-credential", {**_READY}, "none", False),
    ("ready-entra", {**_READY, **_ENTRA}, "entra", False),
    ("ready-entra-with-pat", {**_READY, **_ENTRA, **_PAT}, "entra", False),
    ("ready-pat", {**_READY, **_PAT}, "pat", False),
    ("ready-ids-without-selector", {**_READY, **_IDS, **_PAT}, "pat", False),
    ("ready-other-selector", {**_READY, "VSCE_AUTH": "other", **_PAT}, "pat", False),
    ("ready-other-selector-no-pat", {**_READY, "VSCE_AUTH": "other"}, "none", False),
    ("ready-title-case", {"MARKETPLACE_READY": "True", **_ENTRA}, "entra", False),
    ("ready-upper-case", {"MARKETPLACE_READY": "TRUE", **_PAT}, "pat", False),
    (
        "ready-not-a-boolean",
        {"MARKETPLACE_READY": "yes", **_ENTRA, **_PAT},
        "none",
        False,
    ),
    ("selector-upper-case", {**_READY, **_IDS, "VSCE_AUTH": "ENTRA"}, "entra", False),
    (
        "entra-no-client-id-no-pat",
        {**_READY, "VSCE_AUTH": "entra", "AZURE_TENANT_ID": "tenant"},
        "none",
        True,
    ),
    (
        "entra-no-tenant-id-no-pat",
        {**_READY, "VSCE_AUTH": "entra", "AZURE_CLIENT_ID": "client"},
        "none",
        True,
    ),
    (
        "entra-no-ids-with-pat",
        {**_READY, "VSCE_AUTH": "entra", **_PAT},
        "pat",
        True,
    ),
    (
        "entra-no-tenant-id-with-pat",
        {**_READY, "VSCE_AUTH": "entra", "AZURE_CLIENT_ID": "client", **_PAT},
        "pat",
        True,
    ),
]


@pytest.mark.skipif(
    _SELECTOR_BASH is None, reason="needs a bash that can write $GITHUB_OUTPUT"
)
@pytest.mark.parametrize(
    ("variables", "mode", "warns"),
    [pytest.param(*case[1:], id=case[0]) for case in _SELECTOR_CASES],
)
def test_the_credential_selector_picks_the_documented_mode(
    tmp_path: Path, variables: dict[str, str], mode: str, warns: bool
) -> None:
    # Run the step's own script, so a change to the gate shows up here. A wrong
    # mode fails quietly in production: the publish steps are skipped on a green
    # run, or the publish runs while the switch is off.
    assert _SELECTOR_BASH is not None
    step = _step(_job("publish-vscode.yml", "publish"), _SELECT)
    declared = set(step["env"])
    assert declared == {
        "VSCE_PAT",
        "VSCE_AUTH",
        "AZURE_CLIENT_ID",
        "AZURE_TENANT_ID",
        "MARKETPLACE_READY",
    }
    output = tmp_path / "github-output"
    env = {key: value for key, value in os.environ.items() if key not in declared}
    env.update(variables)
    env["GITHUB_OUTPUT"] = output.as_posix()
    result = subprocess.run(
        [_SELECTOR_BASH, "--noprofile", "--norc", "-c", str(step["run"])],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8").splitlines() == [f"mode={mode}"]
    assert (_INCOMPLETE in result.stdout) is warns, result.stdout
    # The mode is the only thing the step exports, and the token is never echoed.
    assert _TOKEN not in result.stdout + result.stderr
