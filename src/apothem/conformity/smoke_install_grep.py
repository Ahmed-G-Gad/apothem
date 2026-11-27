# SPDX-License-Identifier: MIT

"""Smoke-test the paired install scripts at the repository root.

Why this enforcement exists. The production-ready discipline at section
8.1 ratifies paired install scripts (``scripts/installer/install.sh`` for POSIX shells,
``scripts/installer/install.ps1`` for PowerShell) at the repository root. Each script is
idempotent, prerequisite-checked, and emits a clear next-steps banner
on success. The smoke-install validator catches three failure classes
without touching the host's environment: (a) script absent at the
canonical path, (b) script lacks the strict-mode preamble that prevents
silent error swallowing, (c) script lacks an obvious help / usage
surface that would let an operator inspect prerequisites before piping
to a shell.

Detection strategy. The validator inspects the on-disk shape of the
two scripts under ``--root`` (the repository root). It does NOT execute
the scripts; CI integration runs the scripts under ``bash --noprofile``
and ``pwsh -NoProfile`` separately. The validator's surface is the
script's static form: presence, preamble, prerequisite check, help
flag handling.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import (
    finish_root_report,
    parse_root_args,
    project_file_target,
)
from apothem.conformity._safe_open import (
    REFUSED_OR_GONE,
    read_project_text,
)

# Strict-mode preamble fragments per code-craft-shell rule section 1.
# A script that lacks ANY of the strict-mode fragments listed for its
# shell family is a finding.
BASH_STRICT_FRAGMENTS: Final[tuple[str, ...]] = (
    "set -e",  # also matches set -eu / set -euo pipefail
)
POWERSHELL_STRICT_FRAGMENTS: Final[tuple[str, ...]] = (
    "Set-StrictMode",
    "$ErrorActionPreference",
)

# Help / usage indicators. A script missing both is a finding because
# the operator cannot inspect prerequisites before piping to a shell.
HELP_INDICATORS: Final[tuple[str, ...]] = (
    "--help",
    "-h",
    "-Help",
    "Usage:",
    "USAGE:",
    "usage:",
)

# Prerequisite-check indicators per the production-ready section 8.1
# discipline. The script SHOULD probe for the tools it relies on
# (`git`, `python`, `curl` / `iwr`) before mutating the working tree.
BASH_PREREQ_INDICATORS: Final[tuple[str, ...]] = (
    "command -v",
    "which ",
    "type -p",
)
POWERSHELL_PREREQ_INDICATORS: Final[tuple[str, ...]] = (
    "Get-Command",
    "Test-Path",
)

GREP_NAME: Final[str] = "smoke-install-grep"
RULE_ANCHOR: Final[str] = "production-ready section 8.1 paired install scripts"
EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2


@dataclass(frozen=True)
class Finding:
    """One installer script failing its smoke expectations.

    Pre-conditions: ``script`` is the installer path inspected (an
    ``install`` / ``uninstall`` / ``update`` entry point in either the POSIX or
    the PowerShell family); ``detail`` names the absent guard, flag, or
    idempotence property. Post-conditions: ``rule`` defaults to
    :data:`RULE_ANCHOR` so every finding cites its governing discipline.
    """

    script: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Matcher report for a single sweep of this validator.

    Pre-conditions: ``findings`` holds this module's frozen ``Finding``
    dataclasses. Post-conditions: ``passed`` is ``True`` exactly when
    ``findings`` is empty; :meth:`to_json` emits the serialised payload.
    """

    grep: str
    root: str
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    # Install scripts read; stamped on the report as ``inspected``.
    inspected: int = 0

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, passed,
        findings}``; each finding is flattened through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _has_any(content: str, fragments: tuple[str, ...]) -> bool:
    return any(fragment in content for fragment in fragments)


def _read_script(root: Path, path: Path) -> str | None:
    """Return the text of the script *path*, or None when it is absent.

    A link to a regular file in the project is read at that file (see
    ``project_file_target``). A script that a link or a special file
    replaced since it was looked at, or that is gone, counts as absent too.
    Any other ``OSError`` (a script that is there but cannot be read) is
    raised for the caller to report as unreadable.
    """
    source = project_file_target(root, path)
    if source is None:
        return None
    try:
        return read_project_text(root, source)
    except REFUSED_OR_GONE:
        return None


def _check_bash(root: Path, path: Path, findings: list[Finding]) -> None:
    try:
        content = _read_script(root, path)
    except OSError as exc:
        findings.append(
            Finding(
                script=path.name,
                detail=f"scripts/installer/install.sh unreadable: {exc}",
            )
        )
        return
    if content is None:
        findings.append(
            Finding(
                script=path.name,
                detail="scripts/installer/install.sh absent at repo root, or a link to something other than a regular file in the project",
            )
        )
        return
    if not _has_any(content, BASH_STRICT_FRAGMENTS):
        findings.append(
            Finding(
                script=path.name,
                detail="strict-mode preamble absent (set -e / set -euo pipefail)",
            )
        )
    if not _has_any(content, HELP_INDICATORS):
        findings.append(
            Finding(
                script=path.name,
                detail="help / usage surface absent; operator cannot preview behavior",
            )
        )
    if not _has_any(content, BASH_PREREQ_INDICATORS):
        findings.append(
            Finding(
                script=path.name,
                detail="prerequisite-check absent (command -v / which / type -p)",
            )
        )


def _check_powershell(root: Path, path: Path, findings: list[Finding]) -> None:
    try:
        content = _read_script(root, path)
    except OSError as exc:
        findings.append(
            Finding(
                script=path.name,
                detail=f"scripts/installer/install.ps1 unreadable: {exc}",
            )
        )
        return
    if content is None:
        findings.append(
            Finding(
                script=path.name,
                detail="scripts/installer/install.ps1 absent at repo root, or a link to something other than a regular file in the project",
            )
        )
        return
    if not _has_any(content, POWERSHELL_STRICT_FRAGMENTS):
        findings.append(
            Finding(
                script=path.name,
                detail="strict-mode preamble absent (Set-StrictMode / $ErrorActionPreference)",
            )
        )
    if not _has_any(content, HELP_INDICATORS):
        findings.append(
            Finding(
                script=path.name,
                detail="help / usage surface absent; operator cannot preview behavior",
            )
        )
    if not _has_any(content, POWERSHELL_PREREQ_INDICATORS):
        findings.append(
            Finding(
                script=path.name,
                detail="prerequisite-check absent (Get-Command / Test-Path)",
            )
        )


def check(root: Path) -> GrepResult:
    """Smoke-check the paired install scripts under root."""
    findings: list[Finding] = []
    scripts = (
        root / "scripts/installer/install.sh",
        root / "scripts/installer/install.ps1",
    )
    _check_bash(root, scripts[0], findings)
    _check_powershell(root, scripts[1], findings)
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        passed=not findings,
        findings=findings,
        inspected=sum(
            1 for script in scripts if project_file_target(root, script) is not None
        ),
    )


def _main(argv: list[str]) -> int:
    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.inspected,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
