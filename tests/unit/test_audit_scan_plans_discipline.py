# SPDX-License-Identifier: MIT

"""Unit tests for the plans-discipline scanner.

``apothem.audit.scan_plans_discipline`` walks narrative artifacts for
references to a global user-scope plans directory as a write target — a
host-agnostic plans-discipline violation. It classifies write-intent hits HIGH
and bare references MEDIUM, exempts the discipline documentation by content-
root-relative path, and skips fenced code blocks. The path regex, the
write-intent regex, the exemption predicate, and the per-file scan are pure
transforms; ``main`` runs end-to-end against a fixture inventory in
``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import apothem.audit.scan_plans_discipline as spd


class TestPlansPathRegex:
    def test_matches_every_global_plans_path_form(self) -> None:
        for ref in (
            "see ~/.claude/.plans/suite/PHASE.md",
            "under $HOME/.claude/.plans/suite",
            "at $CLAUDE_PROJECT_DIR/.plans/notes.md",
            r"to %USERPROFILE%\.claude\.plans\suite",
        ):
            assert spd._PLANS_PATH_RE.search(ref), ref

    def test_windows_dot_plans_form_matches(self) -> None:
        # Regression guard: the Windows %USERPROFILE% branch must match the
        # real '.plans' segment (with the leading dot), not a bare 'plans'.
        assert spd._PLANS_PATH_RE.search(r"%USERPROFILE%\.claude\.plans\x")
        assert spd._PLANS_PATH_RE.search(r"%USERPROFILE%/.claude/.plans/x")

    def test_unrelated_paths_do_not_match(self) -> None:
        assert spd._PLANS_PATH_RE.search("the project-local .plans/ directory") is None
        assert spd._PLANS_PATH_RE.search("/var/lib/plans/data") is None


class TestWriteIntentRegex:
    def test_write_verbs_match(self) -> None:
        for verb in ("write", "create", "store", "emit", "land", "materialize"):
            assert spd._WRITE_INTENT_RE.search(f"please {verb} the file")

    def test_non_write_prose_does_not_match(self) -> None:
        assert spd._WRITE_INTENT_RE.search("the path is documented here") is None


class TestIsDisciplineDoc:
    def test_content_root_relative_rules_doc_is_exempt(self) -> None:
        # Regression guard: the exemption keys on the content-root-relative
        # inventory path ('rules/...'), not the stale 'src/apothem/rules/...'.
        assert spd._is_discipline_doc("rules/persistent-conventions-vigilance.md")

    def test_plans_suite_paths_are_exempt(self) -> None:
        assert spd._is_discipline_doc(".plans/suite/spec.md")

    def test_ordinary_file_is_not_a_discipline_doc(self) -> None:
        assert spd._is_discipline_doc("commands/plan.md") is False


class TestScanFile:
    def test_write_intent_line_is_high_severity(self) -> None:
        hits = spd._scan_file("agents/a.md", "write to ~/.claude/.plans/x\n")
        assert len(hits) == 1
        assert hits[0].severity == spd.SEVERITY_HIGH
        assert hits[0].signal.startswith("plans-write-target")

    def test_bare_reference_line_is_medium_severity(self) -> None:
        hits = spd._scan_file("agents/a.md", "the path ~/.claude/.plans/x exists\n")
        assert len(hits) == 1
        assert hits[0].severity == spd.SEVERITY_MEDIUM
        assert hits[0].signal.startswith("plans-path-reference")

    def test_fenced_code_block_lines_are_skipped(self) -> None:
        content = "```\nwrite to ~/.claude/.plans/x\n```\n"
        assert spd._scan_file("agents/a.md", content) == []

    def test_discipline_doc_flag_is_carried_on_hits(self) -> None:
        hits = spd._scan_file(
            "rules/persistent-conventions-vigilance.md",
            "agents must never write to ~/.claude/.plans/x\n",
        )
        assert len(hits) == 1
        assert hits[0].extra["is-discipline-doc"] is True


class TestScanRecord:
    def test_non_narrative_class_is_skipped(self, tmp_path: Path) -> None:
        record = {"class": "memory", "path": "memory/x.md"}
        assert spd._scan_record(record, tmp_path) == []

    def test_narrative_record_is_scanned(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents/a.md").write_text(
            "write to ~/.claude/.plans/x\n", encoding="utf-8"
        )
        record = {"class": "agent", "path": "agents/a.md"}

        hits = spd._scan_record(record, tmp_path)

        assert len(hits) == 1
        assert hits[0].file == "agents/a.md"


class TestMain:
    def test_missing_inventory_returns_error(self, tmp_path: Path) -> None:
        code = spd.main(
            [
                "--inventory",
                str(tmp_path / "absent.json"),
                "--root",
                str(tmp_path),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
        assert code == 1

    def test_full_scan_writes_findings(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents/a.md").write_text(
            "agents must write to ~/.claude/.plans/x\n", encoding="utf-8"
        )
        inventory = tmp_path / "inventory.json"
        inventory.write_text(
            json.dumps({"files": [{"class": "agent", "path": "agents/a.md"}]}),
            encoding="utf-8",
        )
        out = tmp_path / "out.json"

        code = spd.main(
            [
                "--inventory",
                str(inventory),
                "--root",
                str(tmp_path),
                "--output",
                str(out),
            ]
        )

        assert code == 0
        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["scanner"] == "scan_plans_discipline"
        assert doc["hit-count"] == 1
        assert doc["hits"][0]["severity"] == spd.SEVERITY_HIGH
