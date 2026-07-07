# SPDX-License-Identifier: MIT

"""Simulated hook-error scenarios honor the advisory fail-disposition.

Two failure modes are covered: a missing canonical banner fixture (the
validator's exception path returns passed=True silently — the hook
context message documents the two-layer fail-disposition the assistant
honors: the dispatcher is fail-open so the tool call proceeds, and the
assistant surfaces the gap for the operator's decision), and a
non-existent grep module name fed to the orchestrator (a bad ``--check``
argument legitimately exits non-zero, the CI / pre-commit gating signal)."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_missing_banner_fixture_documented_disposition(
    grep_module: ModuleType,
    tmp_path: Path,
    write_guard_path: Path,
    edit_guard_path: Path,
) -> None:
    """When the banner fixture is unreadable, the validator silently
    skips. Both hook context messages document the advisory two-layer
    fail-disposition: the dispatcher is fail-open (the tool call proceeds),
    and the assistant surfaces the gap for the operator before re-issuing.
    Neither message claims a runtime block."""
    (grep_module.SCHEMAS_DIR / "authorship-header.txt").unlink()

    body = "x = 1\n"
    target = tmp_path / "src" / "x.py"
    target.parent.mkdir(parents=True)
    target.write_text(body, encoding="utf-8")

    result = grep_module.check(body, target)

    # Validator skips when fixture absent
    assert result.passed is True

    # Both hook context messages carry the advisory invariant line and
    # document the two-layer fail-disposition (dispatcher fail-open).
    write_text = write_guard_path.read_text(encoding="utf-8")
    edit_text = edit_guard_path.read_text(encoding="utf-8")
    invariant = (
        "Advisory: this hook reports; it does not block. "
        "Mechanical enforcement runs in CI."
    )
    assert invariant in write_text
    assert invariant in edit_text
    assert "**Fail-disposition.**" in write_text
    assert "**Fail-disposition.**" in edit_text
    assert "fail-open" in write_text
    assert "fail-open" in edit_text


def test_unknown_grep_name_exits_nonzero(
    repo_root: Path,
    tmp_path: Path,
    make_envelope: Callable[..., str],
) -> None:
    """A bad ``--check <name>`` argument to the orchestrator returns
    non-zero so the harness blocks the write."""
    orch = repo_root / "src" / "apothem" / "conformity" / "gate.py"
    envelope = make_envelope(
        "Write",
        str(tmp_path / "x.py"),
        content="x = 1\n",
    )
    completed = subprocess.run(
        [sys.executable, str(orch), "--check", "nonexistent-grep", "--hook"],
        input=envelope,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "unknown grep" in completed.stderr
