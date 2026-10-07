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
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "clean-install-gate.yml"


def _load() -> dict:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


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
    # cover every scripts/installer/*.ps1, including any added later.
    steps = _load()["jobs"]["installer-shell-compat"]["steps"]
    parse_steps = [
        s for s in steps if s.get("name", "").startswith("PowerShell 5.1 parse")
    ]
    assert len(parse_steps) == 1, "expected exactly one PowerShell 5.1 parse step"
    file_list = re.search(r"\$files\s*=\s*@\((.*?)\)", parse_steps[0]["run"], re.S)
    assert file_list, "the PowerShell 5.1 parse step must declare a $files list"
    parsed = set(re.findall(r"'([^']+)'", file_list.group(1)))
    installers = {
        path.relative_to(_REPO_ROOT).as_posix()
        for path in (_REPO_ROOT / "scripts" / "installer").glob("*.ps1")
    }
    assert installers, "found no scripts/installer/*.ps1"
    missing = sorted(installers - parsed)
    assert not missing, f"the PowerShell 5.1 parse step skips {missing}"
    for path in sorted(parsed):
        assert (_REPO_ROOT / path).is_file(), f"parse list names a missing {path}"


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
