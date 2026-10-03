# SPDX-License-Identifier: MIT

"""Shipped Python names work in plain words, never by a work-item code.

Every Python file under ``src/apothem`` reaches users through the npm package
and the plugin tree. The gate's advisory rationale in particular is read by
someone with no access to project planning, so each reason and remediation
says what the work is instead of citing a phase number or work-item code.
"""

from __future__ import annotations

import re
from pathlib import Path

from apothem.conformity import gate

_SRC = Path(__file__).resolve().parents[2] / "src" / "apothem"
_PLAN_ID_RE = re.compile(r"phase [0-9]{2}|SR-[0-9]|EN-[0-9]")


def test_shipped_python_has_no_plan_identifiers() -> None:
    hits = [
        f"{path.relative_to(_SRC)}:{number}: {line.strip()}"
        for path in sorted(_SRC.rglob("*.py"))
        if "_vendor" not in path.parts
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _PLAN_ID_RE.search(line)
    ]
    assert hits == []


def test_advisory_rationale_describes_the_work() -> None:
    """Every advisory matcher names a reason and a remediation in plain words."""
    for name, (reason, remediation) in gate._ADVISORY_RATIONALE.items():
        assert reason.strip(), name
        assert remediation.strip(), name
        assert not _PLAN_ID_RE.search(reason + remediation), name
