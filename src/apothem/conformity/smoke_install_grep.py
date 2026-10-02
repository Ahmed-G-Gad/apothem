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


def _check_bash(path: Path, findings: list[Finding]) -> None:
    if not path.exists():
        findings.append(
            Finding(
                script=path.name,
                detail="scripts/installer/install.sh absent at repo root",
            )
        )
        return
    content = path.read_text(encoding="utf-8")
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


def _check_powershell(path: Path, findings: list[Finding]) -> None:
    if not path.exists():
        findings.append(
            Finding(
                script=path.name,
                detail="scripts/installer/install.ps1 absent at repo root",
            )
        )
        return
    content = path.read_text(encoding="utf-8")
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
    _check_bash(scripts[0], findings)
    _check_powershell(scripts[1], findings)
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        passed=not findings,
        findings=findings,
        inspected=sum(1 for script in scripts if script.is_file()),
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top: ``check()`` stays stdlib-only; only
    # the command-line entry needs the shared parser and report stamp.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.inspected,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
