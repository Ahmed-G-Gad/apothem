# SPDX-License-Identifier: MIT

"""Plain-script invocation regression for the conformity-gate hook.

Harness deployments invoke the gate by absolute file path
(``${PYTHON_BIN} ${HARNESS_ROOT}/.apothem/support/conformity/gate.py --hook``), not as
a package module — so ``sys.path`` starts without the directory containing the
``apothem`` package. Before the module-level bootstrap in ``gate.py``, every
matcher importing ``apothem.*`` raised ModuleNotFoundError into the fail-open
isolation boundary: 18 of the 22 per-Write matchers silently no-opped and the
deployed hook degraded to the stdlib-only subset. These tests reproduce the
deployed invocation shape (plain script path, no PYTHONPATH) and pin the
repaired behavior: every registered matcher loads, and an apothem-importing
matcher produces a real finding.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE_SCRIPT = _REPO_ROOT / "src" / "apothem" / "conformity" / "gate.py"

# Content that trips matchers which import the apothem package
# (file_header_grep: missing SPDX header) alongside a stdlib-only matcher
# (bare_except_grep: the bare ``except:`` clause).
_TRIPWIRE_CONTENT = "try:\n    pass\nexcept:\n    pass\n"


def _run_gate_as_plain_script(tmp_path: Path) -> dict:
    """Invoke gate.py exactly as a deployed hook does and return the report."""
    scope = tmp_path / "scope"
    scope.mkdir()
    payload = {
        "tool_input": {
            "file_path": str(scope / "tripwire.py"),
            "content": _TRIPWIRE_CONTENT,
        }
    }
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["APOTHEM_CONFORMITY_SCOPE"] = str(scope)
    completed = subprocess.run(
        [sys.executable, str(_GATE_SCRIPT), "--hook"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        env=env,
    )
    assert completed.stdout, completed.stderr
    return json.loads(completed.stdout)


def test_plain_script_hook_loads_every_matcher(tmp_path: Path) -> None:
    """No matcher errors into the fail-open boundary under script invocation."""
    report = _run_gate_as_plain_script(tmp_path)
    errored = [i["grep"] for i in report["invocations"] if i.get("error")]
    assert errored == [], (
        "matchers failed to load under plain-script invocation "
        f"(the deployed hook shape): {errored}"
    )
    assert report["grep_count"] == len(report["invocations"]) > 0


def test_plain_script_hook_matches_package_invocation_findings(
    tmp_path: Path,
) -> None:
    """An apothem-importing matcher reports findings, same as package mode."""
    report = _run_gate_as_plain_script(tmp_path)
    finding_greps = {i["grep"] for i in report["invocations"] if i.get("findings")}
    # file_header_grep imports the apothem package; bare_except_grep is
    # stdlib-only. Both must fire on the tripwire content.
    assert "file_header_grep" in finding_greps
    assert "bare_except_grep" in finding_greps
    assert report["passed"] is False
