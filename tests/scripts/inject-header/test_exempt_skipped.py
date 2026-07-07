# SPDX-License-Identifier: MIT

"""Exempt-file ``--mode check`` test.

Verifies that files matched by ``src/apothem/schemas/header-exceptions.txt`` (or
files whose filetype family resolves to ``exempt``) return as
``not-applicable`` from the injector — ``--mode check`` exits 0
because there is no divergence to surface.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]


def test_exempt_license_is_not_applicable(
    run_injector: InjectorRunner,
    fixtures_root: Path,
) -> None:
    """A LICENSE-named file (filetype-family exempt) exits 0."""
    fixture = fixtures_root / "exempt" / "LICENSE"
    assert fixture.is_file(), f"missing fixture: {fixture}"
    result = run_injector("--mode", "check", str(fixture))
    assert result.returncode == 0, (
        f"expected exit 0 on exempt LICENSE; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


def test_exempt_json_is_not_applicable(
    run_injector: InjectorRunner,
    fixtures_root: Path,
) -> None:
    """A *.json file (matched by the **/*.json exception glob) exits 0."""
    fixture = fixtures_root / "exempt" / "example.json"
    assert fixture.is_file(), f"missing fixture: {fixture}"
    result = run_injector("--mode", "check", str(fixture))
    assert result.returncode == 0, (
        f"expected exit 0 on exempt JSON; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
