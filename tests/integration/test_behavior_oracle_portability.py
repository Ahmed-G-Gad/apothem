# SPDX-License-Identifier: MIT

"""The behavior-diff oracles capture the same bytes on Windows and Linux.

``scripts/dev/regen-behavior-goldens.py`` rewrites the committed corpus from
these oracles, so any platform-dependent byte in a capture becomes churn in an
unrelated change-set. Three such bytes were observed on Windows: Rich's
legacy-console box substitution, native backslash separators in relative
paths, and a case-insensitive ledger target order. The comparison layer
(``_behavior_canon``) tolerates all three, so these tests compare the parsed
capture against the committed golden exactly, with the perturbations a
Windows shell introduces applied on any host.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest
import rich.console

import apothem.cli

from . import _cli_oracle
from . import _install_driver_oracle as install_oracle

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "behavior-diff"


def test_windows_relative_output_path_is_captured_with_forward_slashes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A relative output path printed with backslashes is stored with slashes."""
    adapter = SimpleNamespace(
        output_path=PureWindowsPath(".cursor/rules/apothem-rules.mdc")
    )
    monkeypatch.setattr(apothem.cli, "_all_adapters", lambda: ([adapter], []))
    _cli_oracle._relative_output_path_spellings.cache_clear()
    try:
        cell = _cli_oracle._normalize_text(
            "│ .cursor\\rules\\apothem-rules.mdc │", home=tmp_path
        )
        raw_json = _cli_oracle._normalize_text(
            '{"output_path": ".cursor\\\\rules\\\\apothem-rules.mdc"}', home=tmp_path
        )
        escape = _cli_oracle._normalize_text('"note": ".cursor\\nrules"', home=tmp_path)
    finally:
        _cli_oracle._relative_output_path_spellings.cache_clear()

    assert cell == "│ .cursor/rules/apothem-rules.mdc │"
    assert raw_json == '{"output_path": ".cursor/rules/apothem-rules.mdc"}'
    assert escape == '"note": ".cursor\\nrules"'


@pytest.mark.parametrize("slug", ["doctor", "harnesses-list", "harnesses-list-json"])
def test_table_capture_ignores_console_color_and_temp_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, slug: str
) -> None:
    """A legacy console, FORCE_COLOR, and a longer temp root leave the capture unchanged."""
    monkeypatch.setattr(rich.console, "detect_legacy_windows", lambda: True)
    monkeypatch.setenv("FORCE_COLOR", "1")
    longer_temp_root = tmp_path / ("t" * 40)
    longer_temp_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(longer_temp_root))
    rows = {row_slug: (argv, seed) for row_slug, argv, seed in _cli_oracle.matrix()}
    argv, seed = rows[slug]

    _cli_oracle.capture_one(tmp_path / "cli", slug, argv, seed_profile=seed)

    captured = json.loads(
        (tmp_path / "cli" / f"{slug}.json").read_text(encoding="utf-8")
    )
    golden = json.loads((GOLDEN / "cli" / f"{slug}.json").read_text(encoding="utf-8"))
    assert captured == golden


def test_ledger_targets_are_stored_in_code_point_order() -> None:
    """Windows and POSIX install orders store the same target order."""
    names = ["NOTICE.md", "__init__.py", "advisory-finding.schema.json"]
    posix_order = sorted(names)
    windows_order = sorted(names, key=str.lower)
    assert windows_order != posix_order

    def record(order: list[str]) -> dict[str, object]:
        return {
            "kind": "install",
            "targets": [
                {"path": f"<ROOT>/.apothem/support/schemas/{name}"} for name in order
            ],
        }

    assert install_oracle._sort_ledger_targets(record(windows_order)) == record(
        posix_order
    )
    assert install_oracle._sort_ledger_targets(record(posix_order)) == record(
        posix_order
    )


def test_real_install_ledger_capture_matches_golden_order(tmp_path: Path) -> None:
    """The claude_code ledger capture keeps the committed target order exactly."""
    out = tmp_path / "corpus"
    install_oracle.capture(out, fast_adapters=[], real_adapters=["claude_code"])

    def records(path: Path) -> list[object]:
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    assert records(out / "ledger" / "claude_code.jsonl") == records(
        GOLDEN / "install_driver" / "ledger" / "claude_code.jsonl"
    )
