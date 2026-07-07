# SPDX-License-Identifier: MIT

"""Shebang preservation test.

A file beginning with ``#!`` keeps its shebang on line 1; the canonical
banner is inserted on line 2 (per spec §4.6.3 insertion-position rule).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]


def test_shebang_preserved_on_python_script(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """Python shebang stays on line 1; banner injected from line 2."""
    target = tmp_path / "tool.py"
    target.write_text(
        "#!/usr/bin/env python3\nprint('hello')\n",
        encoding="utf-8",
    )

    result = run_injector("--mode", "fix-in-place", str(target))
    assert result.returncode == 0, f"fix-in-place failed: {result.stderr}"

    lines = target.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "#!/usr/bin/env python3", (
        f"expected shebang preserved at line 1; got {lines[0]!r}"
    )
    # The narrowed banner is the single SPDX line at line 2, followed by
    # the mandatory blank line at line 3.
    assert "SPDX-License-Identifier" in lines[1], (
        f"expected SPDX prefix at line 2; got {lines[1]!r}"
    )
    assert lines[2] == "", (
        f"expected mandatory blank line below the banner at line 3; got {lines[2]!r}"
    )


def test_shebang_preserved_on_bash_script(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """Bash shebang stays on line 1; banner injected from line 2."""
    target = tmp_path / "tool.sh"
    target.write_text(
        "#!/usr/bin/env bash\necho hello\n",
        encoding="utf-8",
    )

    result = run_injector("--mode", "fix-in-place", str(target))
    assert result.returncode == 0, f"fix-in-place failed: {result.stderr}"

    lines = target.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "#!/usr/bin/env bash", (
        f"expected shebang preserved at line 1; got {lines[0]!r}"
    )
    assert "SPDX-License-Identifier" in lines[1], (
        f"expected SPDX prefix at line 2; got {lines[1]!r}"
    )
    assert lines[2] == "", (
        f"expected mandatory blank line below the banner at line 3; got {lines[2]!r}"
    )
