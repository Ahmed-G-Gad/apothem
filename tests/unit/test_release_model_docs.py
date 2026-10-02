# SPDX-License-Identifier: MIT

"""The release docs describe one release model: additive, nothing rewritten.

The release-cycle runbook adds a commit and a signed tag per release, and the
project keeps every tag, GitHub Release and npm version it has published (npm
versions cannot be replaced). The release-recovery runbook instead described a
"clean-slate-in-place" model: a history safety tag, a force-pushed single
release commit, and rollback by ``reset --hard``. An operator following it
during an incident would rewrite history the release never rewrote.
"""

from __future__ import annotations

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
    for internal in ("D-11", "R-25", "F-F1-03", "elevation"):
        assert internal not in text, f"plan-internal identifier {internal} leaked"
