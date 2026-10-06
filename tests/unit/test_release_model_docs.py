# SPDX-License-Identifier: MIT

"""The release docs describe one release model: additive, nothing rewritten.

Each release adds a commit and a signed tag, and the project keeps every tag,
GitHub Release and npm version it has published (npm versions cannot be
replaced). No runbook tells an operator to force-push, reset or replace
published history, during a release or while recovering from a failed one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_DOCS = Path(__file__).resolve().parents[2] / "site" / "content" / "docs"
_CYCLE = _DOCS / "runbooks" / "release-cycle.mdx"
_RECOVERY = _DOCS / "runbooks" / "release-recovery.mdx"
_POLICY = _DOCS / "governance" / "release-engineering-policy.mdx"

_REWRITE_MARKERS = (
    "force-with-lease",
    "reset --hard",
    "single release commit",
    "clean-slate",
    "history safety tag",
    "history-safety-tag",
)


@pytest.mark.parametrize("path", [_CYCLE, _RECOVERY], ids=["cycle", "recovery"])
def test_no_runbook_prescribes_rewriting_history(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    found = [marker for marker in _REWRITE_MARKERS if marker in text]
    assert not found, f"{path.name} still prescribes {found}"


@pytest.mark.parametrize(
    "path", [_CYCLE, _RECOVERY, _POLICY], ids=["cycle", "recovery", "policy"]
)
def test_docs_state_the_additive_model(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "additive" in text, f"{path.name} does not name the additive release model"
    assert "immutable" in text, f"{path.name} does not say npm versions are immutable"


def test_policy_records_the_release_facade_contradiction() -> None:
    text = _POLICY.read_text(encoding="utf-8")
    assert "release-facade" in text
    assert "three" in text, "the policy records how many releases exist"
    # A published page names work in plain words, never by a work-item code
    # (a capital letter, a dash and two digits, with an optional infix).
    leaked = re.findall(r"\b[DFR]-(?:[A-Z][0-9]-)?[0-9]{2}\b", text)
    assert not leaked, f"work-item codes on a published page: {leaked}"
