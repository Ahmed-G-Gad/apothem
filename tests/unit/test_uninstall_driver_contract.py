# SPDX-License-Identifier: MIT

"""Uninstall-side contract regressions for the shared install driver.

Two invariants pinned here:

1. Uninstall target enumeration skips the same cohort documentation
   companions the install-side appliers skip (``README.md`` and
   ``AGENTS.md``) — a divergent skip set makes uninstall enumerate targets
   install never wrote.
2. ``run_uninstall`` surfaces removal failures: it returns every removal's
   ``MaterializationResult`` and appends the ``kind="uninstall"`` ledger
   marker only when no removal errored, so a failed uninstall never
   masquerades as a completed one.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

# The facade must initialize before its submodules: install_driver_lifecycle
# imports the install_driver facade, which re-exports lifecycle names, so
# importing a submodule first trips the circular-import guard.
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import (
    install_driver_lifecycle as lifecycle,
)
from apothem.harnesses._shared import (
    install_driver_planvalidation as planvalidation,
)
from apothem.harnesses._shared.install_driver_types import MaterializationResult
from apothem.lib.propagation import InstallEntry


@pytest.mark.parametrize(
    "mode",
    ["command_skills", "codex_agents", "gemini_agents", "markdown_commands"],
)
def test_generated_targets_skip_cohort_doc_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Enumeration skips README.md AND AGENTS.md, matching the appliers."""
    src = tmp_path / "cohort"
    src.mkdir()
    (src / "alpha.md").write_text("member", encoding="utf-8")
    (src / "README.md").write_text("doc companion", encoding="utf-8")
    (src / "AGENTS.md").write_text("doc companion", encoding="utf-8")
    monkeypatch.setattr(planvalidation, "resolve_source", lambda _s: src)

    entry = InstallEntry(source="cohort", target="${HARNESS_ROOT}/out", mode=mode)
    targets = planvalidation._generated_targets_for_entry(
        entry,
        harness_root=tmp_path / "root",
        project_root=None,
        exclude=[],
    )

    names = {t.name for t in targets}
    assert not {"README", "README.md", "AGENTS", "AGENTS.md"} & names, names
    assert any(t.name.startswith("alpha") for t in targets), names


def _result(outcome: str) -> MaterializationResult:
    return MaterializationResult(
        outcome=outcome,  # type: ignore[arg-type]
        operation="write_text",
        path="anchor.md",
        message="test outcome",
    )


def _wire_single_sentinel_uninstall(
    monkeypatch: pytest.MonkeyPatch, removal: MaterializationResult
) -> list[object]:
    """Route run_uninstall through one stubbed sentinel removal; capture appends."""
    rules = SimpleNamespace(
        install=[
            InstallEntry(
                source="rules/anchor.md",
                target="${HARNESS_ROOT}/anchor.md",
                mode="sentinel_merge",
            )
        ],
        exclude=[],
    )
    monkeypatch.setattr(install_driver, "load_rules", lambda _n: rules)
    monkeypatch.setattr(lifecycle, "_rendered_template_text", lambda *a, **k: "")
    monkeypatch.setattr(
        lifecycle, "_surgical_remove_from_target", lambda *a, **k: removal
    )
    monkeypatch.setattr(lifecycle, "_remove_data_home", lambda *a, **k: None)
    monkeypatch.setattr(lifecycle.install_ledger, "latest_record", lambda *a, **k: None)
    appended: list[object] = []
    monkeypatch.setattr(lifecycle.install_ledger, "append_record", appended.append)
    return appended


def test_run_uninstall_returns_error_and_skips_ledger_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A removal error is returned to the caller and blocks the uninstall marker."""
    appended = _wire_single_sentinel_uninstall(monkeypatch, _result("error"))

    results = lifecycle.run_uninstall("zed", harness_root=tmp_path)

    assert [r.outcome for r in results] == ["error"]
    assert appended == []


def test_run_uninstall_success_appends_ledger_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean pass returns its results and appends the uninstall marker."""
    appended = _wire_single_sentinel_uninstall(monkeypatch, _result("updated"))

    results = lifecycle.run_uninstall("zed", harness_root=tmp_path)

    assert [r.outcome for r in results] == ["updated"]
    assert len(appended) == 1
