# SPDX-License-Identifier: MIT

"""The gate's ``--hook`` mode honors the hooks-wide kill switch.

``APOTHEM_HOOKS_DISABLE`` silences every dispatcher-routed hook; the conformity
gate hook is registered beside them on the engine install, so the same switch
must silence it too, or an operator troubleshooting hooks still sees one run.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from apothem.conformity import gate


def _run_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str]:
    target = tmp_path / "rules" / "r.md"
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(target), "content": "no frontmatter\n"},
    }
    monkeypatch.setenv(gate.SCOPE_ENV_VAR, str(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    code = gate.main(["gate", "--hook"])
    return code, capsys.readouterr().out


def test_hook_runs_without_the_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("APOTHEM_HOOKS_DISABLE", raising=False)
    _, out = _run_hook(tmp_path, monkeypatch, capsys)
    assert out.strip()


@pytest.mark.parametrize("raw", ["1", "true", "YES", "on"])
def test_switch_silences_the_hook(
    raw: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("APOTHEM_HOOKS_DISABLE", raw)
    code, out = _run_hook(tmp_path, monkeypatch, capsys)
    assert code == gate.EXIT_PASS
    assert out == ""
