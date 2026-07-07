# SPDX-License-Identifier: MIT

"""PowerShell shell-completion regressions.

Two defects are pinned here. First, no PowerShell completion class was
registered, so the emitted script drove ``_APOTHEM_COMPLETE=powershell_complete``
into Click's unregistered-shell branch and every request yielded zero
candidates. Second, Click derives the completion trigger variable from the
detected program name, which under ``python -m apothem`` (the canonical
invocation every shim forwards to) is not ``apothem`` — so no shell's
completion script could engage until the module entry pinned
``complete_var="_APOTHEM_COMPLETE"``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from apothem.cli import main

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMITTED_SCRIPT = (
    _REPO_ROOT / "src" / "apothem" / "cli" / "completions" / "apothem.ps1"
)


def _complete(command_line: str) -> subprocess.CompletedProcess[str]:
    """Drive the env-var protocol exactly as the emitted script does."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_REPO_ROOT / "src")
    env["_APOTHEM_COMPLETE"] = "powershell_complete"
    env["COMP_WORDS"] = command_line
    env["COMP_CWORD"] = str(len(command_line))
    return subprocess.run(
        [sys.executable, "-m", "apothem"],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        env=env,
    )


def test_protocol_completes_command_names() -> None:
    """The powershell_complete instruction yields real candidates."""
    completed = _complete("apothem ver")
    assert completed.returncode == 0, completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line]
    assert lines, "protocol returned no candidates"
    types_values = [line.split(",", 2)[:2] for line in lines]
    assert ["plain", "verify"] in types_values, completed.stdout


def test_protocol_completes_option_values() -> None:
    """Harness-id completion flows through the same protocol."""
    completed = _complete("apothem install --harness ze")
    assert completed.returncode == 0, completed.stderr
    values = [line.split(",", 2)[1] for line in completed.stdout.splitlines() if line]
    assert "zed" in values, completed.stdout


def test_completion_command_emits_registered_class_script() -> None:
    """``apothem completion powershell`` renders the registered class source."""
    result = CliRunner().invoke(main, ["completion", "powershell"])
    assert result.exit_code == 0, result.output
    assert "Register-ArgumentCompleter -Native -CommandName apothem" in result.output
    assert "powershell_complete" in result.output
    assert "_APOTHEM_COMPLETE" in result.output


def test_committed_script_matches_generated_source() -> None:
    """The committed apothem.ps1 is the class output plus the SPDX header."""
    result = CliRunner().invoke(main, ["completion", "powershell"])
    assert result.exit_code == 0, result.output
    expected = "# SPDX-License-Identifier: MIT\n\n" + result.output
    committed = _COMMITTED_SCRIPT.read_text(encoding="utf-8")
    assert committed == expected
