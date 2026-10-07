# SPDX-License-Identifier: MIT

"""The installer-compatibility CI gate fails closed across documented shells.

These assertions run against the in-tree workflow artifact (not live GitHub): the
gate must always run on every pull_request (no path-filter escape that would let a
required check report "skipped but green"), and the installer-shell-compat job
must exercise Linux dash + macOS sh + Windows PowerShell 5.1 so a reintroduced
`??` or bash array cannot regress silently.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "clean-install-gate.yml"
_SCRIPTS = _REPO_ROOT / "scripts"
_REQUIRES_PS_5_1 = re.compile(r"^#Requires\s+-Version\s+5\.1\b", re.I | re.M)


def _load() -> dict:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _step(prefix: str) -> dict:
    steps = _load()["jobs"]["installer-shell-compat"]["steps"]
    matches = [s for s in steps if s.get("name", "").startswith(prefix)]
    assert len(matches) == 1, f"expected exactly one {prefix!r} step"
    return matches[0]


def _repo_paths(paths: Iterable[Path]) -> set[str]:
    return {path.relative_to(_REPO_ROOT).as_posix() for path in paths}


def _on(doc: dict) -> dict:
    # YAML 1.1 parses the bare ``on:`` key as the boolean ``True``.
    triggers = doc.get("on", doc.get(True))
    assert isinstance(triggers, dict), "workflow must declare triggers"
    return triggers


def test_no_path_filter_can_skip_the_required_gate() -> None:
    triggers = _on(_load())
    for event in ("pull_request", "push"):
        config = triggers.get(event)
        if config is None:
            continue
        assert "paths" not in config, f"{event} must not carry a paths filter"
        assert "paths-ignore" not in config, (
            f"{event} must not carry a paths-ignore filter"
        )


def test_gate_always_runs_on_pull_request() -> None:
    triggers = _on(_load())
    assert "pull_request" in triggers
    assert triggers["pull_request"]["branches"] == ["main"]


def test_shell_compat_job_covers_the_three_documented_shells() -> None:
    job = _load()["jobs"]["installer-shell-compat"]
    os_matrix = job["strategy"]["matrix"]["os"]
    assert set(os_matrix) == {"ubuntu-latest", "macos-latest", "windows-latest"}


def test_windows_leg_uses_powershell_5_1_not_pwsh() -> None:
    steps = _load()["jobs"]["installer-shell-compat"]["steps"]
    windows_steps = [s for s in steps if "Windows" in s.get("name", "")]
    assert windows_steps, "the shell-compat job must have a Windows step"
    # `shell: powershell` is Windows PowerShell 5.1; `pwsh` would be 7+ and miss
    # the `??`/5.1-floor regressions C4 guards against.
    assert all(step.get("shell") == "powershell" for step in windows_steps)


def test_windows_leg_parses_every_installer_script() -> None:
    # The Pages build serves the installer scripts and lints them with
    # PSScriptAnalyzer on pwsh 7, whose parser accepts 7.x-only syntax such as
    # `??`. This 5.1 AST parse is the only check that rejects it, so it must
    # cover every scripts/installer/*.ps1 and every script under scripts/ that
    # declares the 5.1 floor (the scripts/apothem.ps1 router), including any
    # added later.
    run = _step("PowerShell 5.1 parse")["run"]
    file_list = re.search(r"\$files\s*=\s*@\((.*?)\)", run, re.S)
    assert file_list, "the PowerShell 5.1 parse step must declare a $files list"
    parsed = set(re.findall(r"'([^']+)'", file_list.group(1)))
    installers = _repo_paths((_SCRIPTS / "installer").glob("*.ps1"))
    assert installers, "found no scripts/installer/*.ps1"
    floor_scripts = _repo_paths(
        path
        for path in _SCRIPTS.rglob("*.ps1")
        if _REQUIRES_PS_5_1.search(path.read_text(encoding="utf-8"))
    )
    assert "scripts/apothem.ps1" in floor_scripts, (
        "the #Requires -Version 5.1 scan no longer finds scripts/apothem.ps1"
    )
    missing = sorted((installers | floor_scripts) - parsed)
    assert not missing, f"the PowerShell 5.1 parse step skips {missing}"
    for path in sorted(parsed):
        assert (_REPO_ROOT / path).is_file(), f"parse list names a missing {path}"


@pytest.mark.parametrize(
    ("check", "file_list"),
    [
        pytest.param("sh -n", r'for f in (.*?);\s*do\s+"\$SH" -n "\$f"', id="sh-n"),
        pytest.param(
            "shellcheck -s sh",
            r"shellcheck -s sh --severity=warning((?:[^\n]*\\\n)*[^\n]*)",
            id="shellcheck",
        ),
    ],
)
def test_posix_leg_checks_every_installer_script(check: str, file_list: str) -> None:
    # The Pages build serves the POSIX installers. It and installer-lint.yml
    # lint them with `shellcheck --severity=error` and no `-s sh`, so the root
    # .shellcheckrc's `shell=bash` applies and no SC3xxx bashism finding is
    # reported. This step's `sh -n` parse and `shellcheck -s sh
    # --severity=warning` are the only checks that report them, so both file
    # lists must cover every scripts/installer/*.sh, including any added later.
    match = re.search(file_list, _step("POSIX shell syntax")["run"], re.S)
    assert match, f"the POSIX gate must run {check} over a file list"
    listed = set(match.group(1).replace("\\", " ").split())
    installers = _repo_paths((_SCRIPTS / "installer").glob("*.sh"))
    assert installers, "found no scripts/installer/*.sh"
    missing = sorted(installers - listed)
    assert not missing, f"the POSIX {check} list skips {missing}"
    for path in sorted(listed):
        assert (_REPO_ROOT / path).is_file(), f"{check} list names a missing {path}"


def test_posix_leg_runs_a_bashism_gate() -> None:
    steps = _load()["jobs"]["installer-shell-compat"]["steps"]
    posix_run = " ".join(
        str(s.get("run", "")) for s in steps if "Linux/macOS" in s.get("name", "")
    )
    assert "shellcheck -s sh" in posix_run  # the bashism fail-closed
    assert "-n " in posix_run  # POSIX parse check


def test_entry_point_shim_smoke_covers_both_runners() -> None:
    # UX-4: a real install must place an `apothem` command on PATH that runs the
    # bundled engine. The gate asserts the shim resolves and runs on both a POSIX
    # and a Windows runner (the dry-run smokes never reach the shim).
    steps = _load()["jobs"]["installer-shell-compat"]["steps"]
    shim_steps = [s for s in steps if "shim smoke" in s.get("name", "")]
    posix = " ".join(
        str(s.get("run", "")) for s in shim_steps if "Linux/macOS" in s.get("name", "")
    )
    windows = " ".join(
        str(s.get("run", "")) for s in shim_steps if "Windows" in s.get("name", "")
    )
    assert posix, "shim smoke must run on a POSIX runner"
    assert windows, "shim smoke must run on a Windows runner"
    # POSIX leg resolves the shim and runs the engine through it.
    assert "command -v apothem" in posix
    assert "apothem harnesses list" in posix
    # Windows leg resolves the shim and runs the engine through it.
    assert "Get-Command apothem" in windows
    assert "apothem harnesses list" in windows
