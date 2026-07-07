# SPDX-License-Identifier: MIT

"""Fix-in-place idempotency test.

Running ``--mode fix-in-place`` twice on the same file MUST produce
identical content. The first run injects (or normalizes) the canonical
banner; the second run detects the canonical banner at the insertion
position and short-circuits to a no-op.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

InjectorRunner = Callable[..., subprocess.CompletedProcess[str]]


def test_fix_in_place_is_idempotent_on_absent_banner(
    tmp_path: Path,
    run_injector: InjectorRunner,
) -> None:
    """Two consecutive fix-in-place runs converge to the same bytes."""
    target = tmp_path / "sample.py"
    target.write_text('"""Sample without banner."""\n', encoding="utf-8")

    first_result = run_injector("--mode", "fix-in-place", str(target))
    assert first_result.returncode == 0, (
        f"first fix-in-place run failed: {first_result.stderr}"
    )
    after_first = target.read_text(encoding="utf-8")

    second_result = run_injector("--mode", "fix-in-place", str(target))
    assert second_result.returncode == 0, (
        f"second fix-in-place run failed: {second_result.stderr}"
    )
    after_second = target.read_text(encoding="utf-8")

    assert after_first == after_second, (
        "expected fix-in-place to be idempotent; second run mutated content"
    )
    assert after_first.startswith("# SPDX-License-Identifier: MIT\n\n"), (
        "expected canonical SPDX header present after first run"
    )
