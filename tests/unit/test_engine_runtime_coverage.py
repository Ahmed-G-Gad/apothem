# SPDX-License-Identifier: MIT

"""Execution-path coverage for the previously-uncovered in-scope runtime modules.

The hooks and statuslines modules are already covered by the bootstrap-wiring,
validate-hooks, and dispatch suites. The genuine remaining uncovered
engine-scoped modules are `cli/reference_export.py` (the documentation
single-source emitter, driven by `site/scripts/update-reference-inventory.mjs`)
and `lib/reporter.py` (a runtime module bundled via `lib/plugin_tree.py`). These
tests exercise them under instrumentation through the `apothem.*` namespace so
coverage attributes correctly.
"""

from __future__ import annotations

import io
import json

from apothem.cli import reference_export
from apothem.lib.reporter import Reporter


def test_reference_export_cli_is_sorted_and_introspects_real_tree() -> None:
    """export_cli walks the real Click tree, sorted, alias-free, deterministic."""
    payload = reference_export.export_cli()
    assert payload["kind"] == "cli"
    names = [str(entry["name"]) for entry in payload["commands"]]
    assert names == sorted(names)
    assert "install" in names  # a real top-level command was introspected
    assert not ({"installing", "Installing", "updating", "Uninstalling"} & set(names))
    # Byte-identical on repeat (the determinism contract).
    assert reference_export.export_cli() == payload


def test_reference_export_harnesses_lists_all_seventeen() -> None:
    """export_harnesses emits every registered adapter with the full record."""
    payload = reference_export.export_harnesses()
    assert payload["kind"] == "harnesses"
    ids = [str(entry["id"]) for entry in payload["harnesses"]]
    assert ids == sorted(ids)
    assert len(ids) == 17
    assert "claude-code" in ids
    for entry in payload["harnesses"]:
        assert {
            "id",
            "display_name",
            "scope",
            "output_format",
            "target_paths",
        } <= set(entry)


def test_reference_export_main_emits_json_for_each_kind(capsys) -> None:
    """main(<kind>) returns 0 and writes parseable JSON for cli and harnesses."""
    assert reference_export.main(["cli"]) == 0
    cli_out = json.loads(capsys.readouterr().out)
    assert cli_out["kind"] == "cli"
    assert reference_export.main(["harnesses"]) == 0
    harness_out = json.loads(capsys.readouterr().out)
    assert harness_out["kind"] == "harnesses"


def test_reference_export_main_rejects_bad_or_missing_kind(capsys) -> None:
    """An unknown or absent kind is a usage error (exit 2), not a crash."""
    assert reference_export.main(["bogus"]) == 2
    assert "usage" in capsys.readouterr().err
    assert reference_export.main([]) == 2


def test_reporter_accumulates_outcomes_and_exit_code() -> None:
    """Reporter writes tagged lines, tracks counts, and reports an exit code."""
    buffer = io.StringIO()
    reporter = Reporter(stream=buffer)
    reporter.section("checks")
    reporter.ok("first")
    reporter.ok("second")
    reporter.warn("a warning")
    reporter.info("a note")
    assert reporter.exit_code == 0
    reporter.fail("a failure")
    assert reporter.exit_code == 1
    reporter.summary()

    out = buffer.getvalue()
    assert "[PASS] first" in out
    assert "[WARN] a warning" in out
    assert "[INFO] a note" in out
    assert "[FAIL] a failure" in out
    assert "=== checks ===" in out
    assert reporter.passed == 2
    assert reporter.failed == 1
    assert reporter.warned == 1
    assert reporter.errors == ["a failure"]
