# SPDX-License-Identifier: MIT

"""``apothem uninstall`` reports the warnings and errors an adapter returns.

An adapter's uninstall returns a ``MaterializationRun``. A warning in it (a
link left in place) prints in plain output and rides the JSON ``warnings``
array; an error in it (a leftover folder that could not be removed) fails the
harness instead of printing "Uninstalled".
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem import cli
from apothem.harnesses._shared.install_driver import MaterializationRun
from apothem.harnesses._shared.install_driver_types import _result


class _Adapter:
    name = "alpha"

    def __init__(self, outcome: str) -> None:
        self._outcome = outcome

    @property
    def output_path(self) -> Path:
        return Path(tempfile.gettempdir()) / "alpha-config"

    def is_installed(self) -> bool:
        return True

    def uninstall(self) -> MaterializationRun:
        return MaterializationRun(
            harness="alpha",
            dry_run=False,
            results=(
                _result("updated", "remove", self.output_path, "removed"),
                _result(self._outcome, "sweep_stale", Path("/old"), "the link /old/x"),
            ),
        )


def _select(monkeypatch: pytest.MonkeyPatch, adapter: _Adapter) -> None:
    monkeypatch.setattr(cli, "_selected_harness_ids", lambda *a, **k: ["alpha"])
    monkeypatch.setattr(cli, "get_harness_entry", lambda hid: hid)
    monkeypatch.setattr(cli, "_load_adapter_for_entry", lambda entry: adapter)
    monkeypatch.setattr(cli, "_require_project_for_selection", lambda ids, root: None)


def _run(*extra: str) -> object:
    return CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "alpha", "--yes", *extra]
    )


def test_a_warning_prints_and_the_uninstall_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _select(monkeypatch, _Adapter("warning"))

    plain = _run()
    as_json = _run("--format", "json")

    assert plain.exit_code == 0  # type: ignore[attr-defined]
    assert "Warning:" in plain.output  # type: ignore[attr-defined]
    assert "the link /old/x" in plain.output  # type: ignore[attr-defined]
    assert "Uninstalled" in plain.output  # type: ignore[attr-defined]
    envelope = json.loads(as_json.output)  # type: ignore[attr-defined]
    assert [w["message"] for w in envelope["warnings"]] == ["the link /old/x"]


def test_an_error_fails_the_uninstall(monkeypatch: pytest.MonkeyPatch) -> None:
    _select(monkeypatch, _Adapter("error"))

    plain = _run()
    as_json = _run("--format", "json")

    assert plain.exit_code == cli._EXIT_EXPECTED  # type: ignore[attr-defined]
    assert "Uninstalled" not in plain.output  # type: ignore[attr-defined]
    assert "the link /old/x" in plain.output  # type: ignore[attr-defined]
    envelope = json.loads(as_json.output)  # type: ignore[attr-defined]
    assert envelope["status"] == "error"
    assert [r["outcome"] for r in envelope["results"]] == ["error"]
