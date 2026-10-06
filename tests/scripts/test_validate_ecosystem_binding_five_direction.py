# SPDX-License-Identifier: MIT

"""validate_ecosystem's binding-five-direction check inspects the real corpus.

The check used to glob ``<repo>/rules`` while the corpus lives under
``src/apothem/``, so it reported "clean across 0 files" in CI. It now resolves
the content root, delegates to the conformity validator, and fails when it
finds nothing to inspect.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from apothem.conformity import binding_five_direction_grep as b5

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "dev" / "validate_ecosystem.py"


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(root),
            "--check",
            "binding-five-direction",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_repository_corpus_is_inspected() -> None:
    """On the repository the check examines every artifact, and all pass."""
    completed = _run(REPO_ROOT)
    match = re.search(
        r"Binding five-direction clean across (\d+) files", completed.stdout
    )
    assert match, completed.stdout
    swept = int(match.group(1))
    assert swept == b5.check(REPO_ROOT).inspected
    assert swept > 150
    assert completed.returncode == 0, completed.stdout


def test_missing_bindings_fails(tmp_path: Path) -> None:
    """A rule without a Bindings section under the checkout layout fails."""
    content = tmp_path / "src" / "apothem"
    (content / "hooks").mkdir(parents=True)
    (content / "rules").mkdir()
    (content / "rules" / "bare-rule.md").write_text("Body.\n", encoding="utf-8")
    completed = _run(tmp_path)
    assert completed.returncode != 0
    assert "rules/bare-rule.md" in completed.stdout


def test_empty_content_root_is_not_clean(tmp_path: Path) -> None:
    """Nothing to inspect is a failure, never 'clean across 0 files'."""
    completed = _run(tmp_path)
    assert completed.returncode != 0
    assert "clean across 0 files" not in completed.stdout
