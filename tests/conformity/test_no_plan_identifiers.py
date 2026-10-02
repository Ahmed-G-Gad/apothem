# SPDX-License-Identifier: MIT

"""Shipped Python carries no plan-internal identifiers.

The gate's advisory rationale once named private plan phases and work items by
their internal codes. Those strings ship in the npm package and the plugin
tree, where they mean nothing to a reader and break the release-facade rule.
The advisory notes now describe the work in plain words; this test keeps it
that way.
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
