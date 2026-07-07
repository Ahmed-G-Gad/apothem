# SPDX-License-Identifier: MIT

"""Malformed-banner ``--mode check`` test.

Verifies that ``--mode check`` exits non-zero on a Python file whose
banner is present but drifted (wrong website URL). The fixture is
constructed at runtime via ``tmp_path`` to avoid checking a malformed
banner into the long-lived fixture tree.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]


MALFORMED_DRIFTED_WEBSITE: str = (
    "#  Copyright (c) Ahmed G. Gad ----------------------  #\n"
    "#      Website:   https://wrong-domain.com            #\n"
    "#      Email:     mailto:me@ahmedgad.com              #\n"
    "#      Github:    https://github.com/ahmed-g-gad      #\n"
    "#  All rights reserved -----------------------------  #\n"
    "\n"
    '"""Malformed sample with a drifted Website URL in the banner."""\n'
)


def test_malformed_drifted_website_fails_check(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """A Python banner with a drifted Website URL exits non-zero."""
    target = tmp_path / "sample.py"
    target.write_text(MALFORMED_DRIFTED_WEBSITE, encoding="utf-8")

    result = run_injector("--mode", "check", str(target))

    assert result.returncode != 0, (
        f"expected non-zero exit on malformed banner; got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
