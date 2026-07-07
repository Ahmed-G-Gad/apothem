# SPDX-License-Identifier: MIT

"""Absent-banner ``--mode check`` test.

Verifies that ``--mode check`` exits non-zero on an applicable file
that lacks any banner. The fixture is constructed via ``tmp_path``
because shipping an absent-banner file at a long-lived fixture path
would be flagged by the injector itself when it walks the codebase.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]


def test_absent_python_fails_check(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """A Python file with no banner exits non-zero in check mode."""
    target = tmp_path / "sample.py"
    target.write_text('"""Sample without the canonical banner."""\n', encoding="utf-8")

    result = run_injector("--mode", "check", str(target))

    assert result.returncode != 0, (
        f"expected non-zero exit on absent banner; got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
