# SPDX-License-Identifier: MIT

"""Planted defects fail the corpus gate in its CI form (``--all --strict``).

The gate's standalone sweep once passed vacuously: naming-grep inspected no
component when handed a relative root, and the five-direction Bindings check
ran only in a developer script that globbed an empty directory. These tests
plant a misnamed file and a rule without a ``## Bindings`` section into a
minimal content tree and assert that ``gate --all --strict`` exits with the
findings-block code and attributes each failure to the validator that owns it,
while the same tree without the plants passes both validators.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from apothem.conformity import gate

_REPO_ROOT = Path(__file__).resolve().parents[2]

_FULL_BINDINGS = """
## Bindings (§0.j five-direction)

- **Drives →** the downstream surface.
- **Satisfies →** the end state.
- **Established by ↑** the anchor.
- **Gated by ←** the activation condition.
- **Cross-bound with ↔** the sibling.
"""


def _gate(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(_REPO_ROOT / "src"))
    env.pop("APOTHEM_CONFORMITY_STRICT", None)
    return subprocess.run(
        [sys.executable, "-m", "apothem.conformity.gate", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=600,
    )


def _rule(path: Path, bindings: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nname: x\ndescription: y\n---\n\n<!-- SPDX-License-Identifier: MIT -->\n"
        f"\nBody.\n{bindings}",
        encoding="utf-8",
    )


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A minimal checkout-layout content tree that both validators accept."""
    rules = tmp_path / "src" / "apothem" / "rules"
    _rule(rules / "sample-rule.md", _FULL_BINDINGS)
    return tmp_path


def _entry(report: dict[str, object], name: str) -> dict[str, object]:
    results = report["results"]
    assert isinstance(results, list)
    return next(e for e in results if e["validator"] == name)


def test_planted_validators_run_under_all() -> None:
    """Both validators are registered, so ``--all`` dispatches them."""
    assert "naming-grep" in gate.STANDALONE_MODULES
    assert "binding-five-direction-grep" in gate.STANDALONE_MODULES


def test_unplanted_tree_passes_both_validators(tree: Path) -> None:
    for name in ("naming-grep", "binding-five-direction-grep"):
        completed = _gate("--check", name, ".", "--strict", cwd=tree)
        assert completed.returncode == gate.EXIT_PASS, completed.stdout


def test_planted_defects_fail_all_strict(tree: Path) -> None:
    """A misnamed file and a rule missing Bindings fail ``--all --strict .``."""
    rules = tree / "src" / "apothem" / "rules"
    _rule(rules / "BadName_Rule.md", _FULL_BINDINGS)
    _rule(rules / "missing-bindings.md", "")

    completed = _gate("--all", "--strict", ".", cwd=tree)

    assert completed.returncode == gate.EXIT_FAIL
    report = json.loads(completed.stdout)
    naming = _entry(report, "naming-grep")
    assert naming["passed"] is False
    assert "BadName_Rule.md" in str(naming["output"])
    bindings = _entry(report, "binding-five-direction-grep")
    assert bindings["passed"] is False
    assert "rules/missing-bindings.md" in str(bindings["output"])
    assert "BadName_Rule.md" not in str(bindings["output"])
