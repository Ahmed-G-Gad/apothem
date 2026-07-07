# SPDX-License-Identifier: MIT

"""Canonical-banner ``--mode check`` tests across variant families.

Verifies that ``--mode check`` exits 0 on files whose banner is already
canonical for their variant family — hash (Python), hash + shebang
(Bash), and html (Markdown).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]


def test_canonical_python_passes_check(
    run_injector: InjectorRunner,
    fixtures_root: Path,
) -> None:
    """A Python file with the hash-form banner exits 0 in check mode."""
    fixture = fixtures_root / "canonical" / "sample.py"
    assert fixture.is_file(), f"missing fixture: {fixture}"
    result = run_injector("--mode", "check", str(fixture))
    assert result.returncode == 0, (
        f"expected exit 0 on canonical Python; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


def test_canonical_bash_with_shebang_passes_check(
    run_injector: InjectorRunner,
    fixtures_root: Path,
) -> None:
    """A Bash file with shebang + hash banner at line 2 exits 0."""
    fixture = fixtures_root / "canonical" / "sample.sh"
    assert fixture.is_file(), f"missing fixture: {fixture}"
    result = run_injector("--mode", "check", str(fixture))
    assert result.returncode == 0, (
        f"expected exit 0 on canonical Bash; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


def test_canonical_markdown_passes_check(
    run_injector: InjectorRunner,
    fixtures_root: Path,
) -> None:
    """A Markdown file with the html-block banner exits 0."""
    fixture = fixtures_root / "canonical" / "sample.md"
    assert fixture.is_file(), f"missing fixture: {fixture}"
    result = run_injector("--mode", "check", str(fixture))
    assert result.returncode == 0, (
        f"expected exit 0 on canonical Markdown; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
