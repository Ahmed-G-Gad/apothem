# SPDX-License-Identifier: MIT

"""Every pull request runs the installer lint the Pages build runs.

``publish-static-site.yml`` lints its ``site/dist/`` copies of the installers
with shellcheck and PSScriptAnalyzer before it deploys GitHub Pages, but it runs
only on pushes to ``main`` that touch its paths and on manual dispatch, never on
a pull request. A PSScriptAnalyzer warning that no pull-request check ran once
stopped that build after the merge, and Pages stopped updating.
``installer-lint.yml`` runs the same commands on ``scripts/installer/`` for every
pull request.

These assertions run against the in-tree workflow files, not live GitHub. They
keep the two workflows in lockstep, so a lint change made in one place cannot
let a finding pass the pull request and then fail the deploy.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"
_PAGES_DIR = "site/dist/"
_SOURCE_DIR = "scripts/installer/"
_SETTINGS = "-Settings PSScriptAnalyzerSettings.psd1"

# Static Site build step -> its installer-lint.yml twin.
_MIRRORED_STEPS = [
    ("Validate synced shell scripts", "Validate installer shell scripts"),
    ("Validate synced PowerShell scripts", "Validate installer PowerShell scripts"),
]
_ANALYZER_STEPS = [
    ("publish-static-site.yml", "build", "Validate synced PowerShell scripts"),
    ("installer-lint.yml", "installer-lint", "Validate installer PowerShell scripts"),
]
# Step conditions that still run the lint on every pull request.
_ALWAYS_RUNS = (None, "${{ !cancelled() }}")


def _load(name: str) -> dict:
    return yaml.safe_load((_WORKFLOWS / name).read_text(encoding="utf-8"))


def _on(doc: dict) -> dict:
    # YAML 1.1 parses the bare ``on:`` key as the boolean ``True``.
    triggers = doc.get("on", doc.get(True))
    assert isinstance(triggers, dict), "workflow must declare triggers"
    return triggers


def _step(job: dict, name: str) -> dict:
    matches = [step for step in job["steps"] if step.get("name") == name]
    assert len(matches) == 1, f"expected exactly one step named {name!r}"
    return matches[0]


def _run_setting(doc: dict, job: dict, step: dict, key: str) -> str | None:
    """Resolve ``shell`` or ``working-directory`` the way the runner does."""
    for scope in (
        step,
        job.get("defaults", {}).get("run", {}),
        doc.get("defaults", {}).get("run", {}),
    ):
        if key in scope:
            return str(scope[key])
    return None


@pytest.mark.parametrize(("pages_name", "lint_name"), _MIRRORED_STEPS)
def test_lint_step_runs_the_pages_command_on_the_sources(
    pages_name: str, lint_name: str
) -> None:
    pages_doc = _load("publish-static-site.yml")
    lint_doc = _load("installer-lint.yml")
    pages_job = pages_doc["jobs"]["build"]
    lint_job = lint_doc["jobs"]["installer-lint"]
    pages = _step(pages_job, pages_name)
    lint = _step(lint_job, lint_name)

    assert _PAGES_DIR in pages["run"], f"{pages_name!r} must lint {_PAGES_DIR}"
    assert lint["run"] == pages["run"].replace(_PAGES_DIR, _SOURCE_DIR), (
        f"{lint_name!r} in installer-lint.yml must run the command of "
        f"{pages_name!r} in publish-static-site.yml on {_SOURCE_DIR}; "
        "change both steps together"
    )
    for key in ("shell", "working-directory"):
        assert _run_setting(lint_doc, lint_job, lint, key) == _run_setting(
            pages_doc, pages_job, pages, key
        ), f"{lint_name!r} and {pages_name!r} must use the same {key}"
    assert not lint.get("continue-on-error"), f"{lint_name!r} must fail the job"
    assert not pages.get("continue-on-error"), f"{pages_name!r} must fail the job"
    # A step skipped by its condition reports success and lints nothing.
    assert lint.get("if") in _ALWAYS_RUNS, f"{lint_name!r} must run on every PR"
    assert "if" not in pages, f"{pages_name!r} must run on every Pages build"


def test_both_lints_run_on_the_same_pinned_runner_image() -> None:
    # The linters are the image's preinstalled ones. A `-latest` label moves to a
    # new image over weeks, so the two jobs could lint with different versions,
    # and PSScriptAnalyzer reports more alias findings on Windows than on Linux.
    pages_runner = _load("publish-static-site.yml")["jobs"]["build"]["runs-on"]
    lint_runner = _load("installer-lint.yml")["jobs"]["installer-lint"]["runs-on"]
    assert lint_runner == pages_runner
    assert not str(lint_runner).endswith("-latest"), (
        "pin a runner image, not a -latest label"
    )


def test_both_shellchecks_read_the_same_rc_file() -> None:
    # shellcheck reads the nearest .shellcheckrc or shellcheckrc at or above each
    # script's own directory. One below the repository root on either path would
    # change only that lint; the static export copies site/public/ into site/dist/.
    for folder in ("scripts/installer", "scripts", "site", "site/public"):
        for name in (".shellcheckrc", "shellcheckrc"):
            assert not (_REPO_ROOT / folder / name).exists(), (
                f"{folder}/{name} would apply to only one of the two lints"
            )


@pytest.mark.parametrize(("workflow", "job", "step"), _ANALYZER_STEPS)
def test_analyzer_filters_live_only_in_the_settings_file(
    workflow: str, job: str, step: str
) -> None:
    # A command-line filter is merged with the settings file's values, so an
    # exclusion added at one call site would silently diverge from the other.
    run = _step(_load(workflow)["jobs"][job], step)["run"]
    assert _SETTINGS in run, f"{step!r} must pass {_SETTINGS}"
    for flag in ("-Severity", "-ExcludeRule", "-IncludeRule"):
        assert flag not in run, (
            f"{step!r} passes {flag}; set it in PSScriptAnalyzerSettings.psd1"
        )


_PWSH = shutil.which("pwsh") or shutil.which("powershell")
# The lint steps' analyzer call, run from the repository root under the 'Stop'
# preference the runner's pwsh shell prepends. The folder arrives through the
# environment, so no path is quoted into PowerShell source, and it is escaped
# because -Path expands wildcards: a '[' in the name would be read as a pattern
# and match no file or fail as invalid. Exit 3 marks a PowerShell that cannot
# load PSScriptAnalyzer: missing, or older than the module supports.
_ANALYZE = "; ".join(
    (
        "$ErrorActionPreference = 'Stop'",
        "try { Import-Module PSScriptAnalyzer } catch { exit 3 }",
        "$dir = [Management.Automation.WildcardPattern]::Escape($env:LINT_DIR)",
        f"Invoke-ScriptAnalyzer -Path $dir {_SETTINGS}"
        " | ForEach-Object { '{0} {1}' -f $_.Severity, $_.RuleName }",
    )
)


@pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")
def test_settings_make_the_analyzer_report_parse_errors(tmp_path: Path) -> None:
    # The analyzer reports a script that does not parse only as a ParseError
    # record, so a Severity list without that value lets it pass both lints.
    (tmp_path / "broken.ps1").write_text("function Broken {\n", encoding="utf-8")
    assert _PWSH is not None
    result = subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _ANALYZE,
        ],
        cwd=_REPO_ROOT,
        env={
            **os.environ,
            "LINT_DIR": str(tmp_path),
            "NO_COLOR": "1",
            "POWERSHELL_TELEMETRY_OPTOUT": "1",
        },
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode == 3:
        pytest.skip("PSScriptAnalyzer does not load in this PowerShell")
    assert result.returncode == 0, result.stdout + result.stderr
    findings = result.stdout.splitlines()
    assert any(line.startswith("ParseError ") for line in findings), (
        f"no ParseError finding for a script that does not parse ({findings}); "
        "keep 'ParseError' in Severity in PSScriptAnalyzerSettings.psd1"
    )


_BASH = find_test_bash()


@pytest.mark.skipif(_BASH is None, reason=SKIP_REASON)
def test_pages_lints_byte_copies_of_the_linted_sources(tmp_path: Path) -> None:
    # The pull-request lint covers what the Pages build serves only while each
    # script the Pages lint sees is a copy of a file in scripts/installer/.
    sources = _REPO_ROOT / "scripts" / "installer"
    shutil.copytree(sources, tmp_path / "scripts" / "installer")
    dist = tmp_path / "site" / "dist"
    dist.mkdir(parents=True)
    sync = _step(
        _load("publish-static-site.yml")["jobs"]["build"],
        "Sync canonical install scripts into site/dist/",
    )

    subprocess.run([_BASH, "-c", sync["run"]], cwd=tmp_path, check=True, timeout=60)

    staged = sorted(path for path in dist.iterdir() if path.suffix in {".sh", ".ps1"})
    assert {path.suffix for path in staged} == {".sh", ".ps1"}, (
        "the sync step staged no shell or PowerShell script for the Pages lint"
    )
    for copy in staged:
        source = sources / copy.name
        assert source.is_file(), (
            f"site/dist/{copy.name} has no scripts/installer/ source"
        )
        assert copy.read_bytes() == source.read_bytes(), copy.name


def test_installer_lint_always_reports_on_pull_requests() -> None:
    # A required check whose workflow a paths filter skips stays "Pending" and
    # blocks the merge, so this one runs on every pull request to main.
    doc = _load("installer-lint.yml")
    pull_request = _on(doc)["pull_request"]
    assert pull_request["branches"] == ["main"]
    assert "paths" not in pull_request, "the required check must not be path-filtered"
    assert "paths-ignore" not in pull_request, (
        "the required check must not be path-filtered"
    )
    # A job skipped by `if:` reports success and would gate nothing.
    assert "if" not in doc["jobs"]["installer-lint"]
