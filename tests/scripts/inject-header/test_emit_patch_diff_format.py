# SPDX-License-Identifier: MIT

"""Emit-patch unified-diff format test.

``--mode emit-patch`` must print a valid unified diff to stdout when
divergence is detected, and that diff must contain the canonical banner
information lines as additions.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]


def test_emit_patch_outputs_valid_unified_diff(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """emit-patch outputs a unified diff containing the banner additions."""
    target = tmp_path / "sample.py"
    target.write_text('"""Sample without banner."""\n', encoding="utf-8")

    result = run_injector("--mode", "emit-patch", str(target))

    assert result.returncode == 0, (
        f"emit-patch must exit 0 on a generated diff; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    # Unified-diff structural invariants.
    assert "--- a/" in result.stdout, "expected unified-diff source header"
    assert "+++ b/" in result.stdout, "expected unified-diff target header"
    assert "@@ " in result.stdout, "expected hunk-header line"
    # Substantive invariant: the canonical SPDX header is added.
    assert "+# SPDX-License-Identifier: MIT" in result.stdout, (
        "expected the canonical SPDX header as an addition in the diff"
    )
    # The fix-in-place mode is read-only on emit-patch — file unchanged.
    assert target.read_text(encoding="utf-8") == '"""Sample without banner."""\n', (
        "emit-patch must not modify the file"
    )
