# SPDX-License-Identifier: MIT

"""Fail when the single-sourced pip pin drifts across the CI workflows.

The pip pin (`PIP_PIN_VERSION`) closes CVE-2026-13346 and is set once per
workflow file at the top-level ``env:`` block, referenced from every
``python -m pip install "pip==${PIP_PIN_VERSION}"`` step. This check enforces
that single-source contract mechanically so a security bump cannot silently
land in some workflows and not others:

1. Every ``.github/workflows/*.yml`` that installs pip declares a top-level
   ``PIP_PIN_VERSION`` and they all agree on one value.
2. No workflow carries a literal ``pip==<version>`` install line — those must
   go through the env var so the drift check can see them.

Exit 0 when the pin is coherent, 1 (with a diagnostic) on any drift. The
script is dependency-free (line-oriented parsing, no PyYAML) so it runs on the
conformity-gate execution path without extra packages.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"

# A top-level `PIP_PIN_VERSION: "x.y.z"` env entry (quotes optional).
_PIN_ENV_RE = re.compile(
    r'^\s*PIP_PIN_VERSION:\s*["\']?(?P<version>[0-9]+(?:\.[0-9]+)*)["\']?\s*$'
)
# A literal `pip install pip==x.y.z` — the drift shape the env var replaces.
_PIN_LITERAL_RE = re.compile(r"pip\s+install\s+.*\bpip==[0-9]")
# Any step that installs pip via the single-sourced env var.
_PIN_ENV_USE_RE = re.compile(r"pip==\$\{PIP_PIN_VERSION\}")


def _iter_workflows() -> list[Path]:
    return sorted(_WORKFLOW_DIR.glob("*.yml"))


def main() -> int:
    """Report pip-version pin drift across the workflow set; return the exit.

    Post-conditions: returns ``1`` when the workflow directory is absent, when
    any workflow installs pip at a literal version instead of the shared
    environment pin, or when a workflow declares no pin at all. Returns ``0``
    when every workflow resolves pip through the single declared pin, which is
    what keeps one bump from having to be mirrored by hand across the matrix.
    """
    if not _WORKFLOW_DIR.is_dir():
        print(f"error: workflow directory not found: {_WORKFLOW_DIR}", file=sys.stderr)
        return 1

    pins: dict[str, str] = {}
    literal_offenders: list[str] = []
    missing_env: list[str] = []

    for workflow in _iter_workflows():
        text = workflow.read_text(encoding="utf-8")
        rel = workflow.relative_to(_REPO_ROOT).as_posix()

        declared: str | None = None
        for line in text.splitlines():
            match = _PIN_ENV_RE.match(line)
            if match:
                declared = match.group("version")
                break

        uses_env = bool(_PIN_ENV_USE_RE.search(text))
        has_literal = bool(_PIN_LITERAL_RE.search(text))

        if has_literal:
            literal_offenders.append(rel)

        if declared is not None:
            pins[rel] = declared
        elif uses_env:
            # References the env var but never declares it — a broken pin source.
            missing_env.append(rel)

    problems: list[str] = []

    if literal_offenders:
        joined = ", ".join(literal_offenders)
        problems.append(
            "literal `pip==<version>` install line(s) found; route the pin "
            f"through the PIP_PIN_VERSION env var instead: {joined}"
        )

    if missing_env:
        joined = ", ".join(missing_env)
        problems.append(
            "workflow(s) reference ${PIP_PIN_VERSION} but declare no top-level "
            f"PIP_PIN_VERSION env: {joined}"
        )

    distinct = sorted(set(pins.values()))
    if len(distinct) > 1:
        detail = "; ".join(f"{path} -> {ver}" for path, ver in sorted(pins.items()))
        problems.append(
            f"PIP_PIN_VERSION disagrees across workflows ({', '.join(distinct)}): "
            f"{detail}"
        )

    if problems:
        print("pip-pin drift detected:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if not pins:
        print(
            "error: no workflow declares PIP_PIN_VERSION; the pin single-source "
            "is missing",
            file=sys.stderr,
        )
        return 1

    print(f"pip pin coherent across {len(pins)} workflow(s): pip=={distinct[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
