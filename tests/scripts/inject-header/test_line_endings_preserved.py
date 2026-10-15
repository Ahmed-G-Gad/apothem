# SPDX-License-Identifier: MIT

"""Fix-in-place keeps each file's line endings.

The injector used to read with universal newlines and write with
``Path.write_text``, which on Windows turned every ``\\n`` of an LF file into
``\\r\\n``. A rewrite MUST keep an LF file LF and a CRLF file CRLF on every host.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]


def test_lf_file_stays_lf(tmp_path: Path, run_injector: InjectorRunner) -> None:
    """An LF file gains the header and keeps LF line endings only."""
    target = tmp_path / "sample.py"
    target.write_bytes(b'"""Sample without a header."""\n\nVALUE = 1\n')

    result = run_injector("--mode", "fix-in-place", str(target))
    assert result.returncode == 0, result.stderr

    data = target.read_bytes()
    assert data.startswith(b"# SPDX-License-Identifier: MIT\n")
    assert b"\r" not in data


def test_crlf_file_stays_crlf(tmp_path: Path, run_injector: InjectorRunner) -> None:
    """A CRLF file gains the header and keeps CRLF on every line."""
    target = tmp_path / "sample.py"
    target.write_bytes(b'"""Sample without a header."""\r\n\r\nVALUE = 1\r\n')

    result = run_injector("--mode", "fix-in-place", str(target))
    assert result.returncode == 0, result.stderr

    data = target.read_bytes()
    assert data.startswith(b"# SPDX-License-Identifier: MIT\r\n")
    assert data.count(b"\n") == data.count(b"\r\n")
