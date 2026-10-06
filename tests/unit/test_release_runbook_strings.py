# SPDX-License-Identifier: MIT

"""The release-cycle runbook's expected outputs match what the tools print.

The runbook told the maintainer to expect ``apothem X.Y.Z`` from
``--version`` and a ``## [X.Y.Z] — YYYY-MM-DD`` changelog heading. The CLI
prints ``Apothem, version X.Y.Z`` (every install path runs ``python -m
apothem``) and the changelog uses a hyphen, so a correct release read as a
failure. These tests derive the expected strings from the real CLI and the
real CHANGELOG.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from apothem import __version__

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNBOOK = _REPO_ROOT / "site" / "content" / "docs" / "runbooks" / "release-cycle.mdx"


def _cli_version_line() -> str:
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    completed = subprocess.run(
        [sys.executable, "-m", "apothem", "--version"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_runbook_version_output_matches_the_cli() -> None:
    expected = _cli_version_line().replace(__version__, "X.Y.Z")
    assert expected != _cli_version_line(), "the CLI no longer prints the version"
    text = _RUNBOOK.read_text(encoding="utf-8")
    assert f"`{expected}`" in text, f"runbook never shows the real output {expected!r}"
    stale = re.findall(r"`apothem X\.Y\.Z`", text)
    assert not stale, "runbook still expects `apothem X.Y.Z`"


def test_runbook_changelog_heading_matches_the_changelog() -> None:
    headings = re.findall(
        r"^## \[\d+\.\d+\.\d+\][^\n]*$",
        (_REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert headings
    for heading in headings:
        assert re.fullmatch(r"## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}", heading), (
            heading
        )
    text = _RUNBOOK.read_text(encoding="utf-8")
    assert "`## [X.Y.Z] - YYYY-MM-DD`" in text
    assert "## [X.Y.Z] —" not in text
