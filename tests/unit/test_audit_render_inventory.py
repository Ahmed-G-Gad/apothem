# SPDX-License-Identifier: MIT

"""Unit tests for the inventory Markdown renderer.

``apothem.audit.render_inventory`` turns the machine-readable
``inventory.json`` into the human-readable ``inventory.md`` mirror: aggregate
stats, per-class enumerated tables, aggregated views for the large classes, a
narrative-surface index, and the recursive plan-suite inventory. Each section
renderer is a pure transform over the inventory payload, so they are covered
directly; ``main`` is exercised end-to-end through a fixture written to
``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apothem.audit.render_inventory import (
    EXIT_ERROR,
    EXIT_OK,
    FLAT_TABLE_LIMIT,
    load_inventory,
    main,
    parse_arguments,
    render_aggregate_section,
    render_aggregated_section,
    render_inventory,
    render_narrative_surface_section,
    render_per_class_section,
    render_plan_suites_section,
    render_skipped_section,
)


def _record(
    path: str,
    cls: str,
    *,
    lines: int | None = 10,
    sha: str = "abcdef0123456789",
    header_status: str = "present",
    size: int = 100,
) -> dict[str, Any]:
    """Build one inventory file record."""
    return {
        "path": path,
        "class": cls,
        "line-count": lines,
        "sha256": sha,
        "header-status": header_status,
        "size": size,
    }


def _inventory(
    files: list[dict[str, Any]],
    *,
    skipped: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble an inventory payload with derived aggregate maps."""
    by_class: dict[str, int] = {}
    by_header_status: dict[str, int] = {}
    by_header_variant: dict[str, int] = {}
    for record in files:
        by_class[record["class"]] = by_class.get(record["class"], 0) + 1
        by_header_status[record["header-status"]] = (
            by_header_status.get(record["header-status"], 0) + 1
        )
        by_header_variant["spdx"] = by_header_variant.get("spdx", 0) + 1
    return {
        "root": "/repo",
        "generated-at": "2026-06-22T00:00:00+00:00",
        "total-files": len(files),
        "skipped-directories": skipped or [],
        "by-class": by_class,
        "by-header-status": by_header_status,
        "by-header-variant": by_header_variant,
        "files": files,
    }


class TestLoadInventory:
    """Inventory deserialisation.

    Covers that the JSON payload round-trips unchanged.
    """

    def test_round_trips_the_json_payload(self, tmp_path: Path) -> None:
        path = tmp_path / "inv.json"
        payload = _inventory([_record("a.md", "docs")])
        path.write_text(json.dumps(payload), encoding="utf-8")

        assert load_inventory(path) == payload


class TestRenderAggregateSection:
    """Rendering the aggregate distribution tables.

    Covers the three tables and their thousands separators, plus the omission
    rules that keep zero-count rows — classes, header statuses, and variants —
    out of the output rather than printing empty rows.
    """

    def test_emits_three_distribution_tables_with_thousands_separator(self) -> None:
        files = [_record(f"a{i}.md", "docs") for i in range(1500)]
        lines = render_aggregate_section(_inventory(files))
        body = "\n".join(lines)

        assert "## Aggregate stats" in body
        assert "**Root:** `/repo`" in body
        assert "### By class" in body
        assert "### By header status" in body
        assert "### By header variant" in body
        # Thousand-separator formatting on the total.
        assert "1,500" in body

    def test_zero_count_classes_are_omitted(self) -> None:
        inv = _inventory([_record("a.md", "docs")])
        inv["by-class"]["agent"] = 0  # explicit zero -> skipped

        body = "\n".join(render_aggregate_section(inv))

        assert "`docs`" in body
        assert "| `agent` |" not in body

    def test_zero_count_header_status_and_variant_are_omitted(self) -> None:
        inv = _inventory([_record("a.md", "docs", header_status="present")])
        inv["by-header-status"]["absent"] = 0  # explicit zero -> skipped
        inv["by-header-variant"]["legacy"] = 0  # explicit zero -> skipped

        body = "\n".join(render_aggregate_section(inv))

        assert "| `present` |" in body
        assert "| `absent` |" not in body
        assert "| `legacy` |" not in body


class TestRenderPerClassSection:
    """Rendering the per-class file enumeration.

    Covers the flat enumeration with path, line count, and digest; the em-dash
    rendering when a line count is absent; and the fallback to aggregation once
    a class exceeds the flat-listing limit.
    """

    def test_enumerates_small_classes_with_path_lines_sha(self) -> None:
        files = [
            _record("agents/b.md", "agent", lines=20, sha="deadbeefcafe0000"),
            _record("agents/a.md", "agent"),
        ]
        body = "\n".join(render_per_class_section(_inventory(files)))

        assert "### agent (2)" in body
        # Sorted by path -> a before b.
        assert body.index("agents/a.md") < body.index("agents/b.md")
        # SHA is truncated to a 12-char prefix.
        assert "`deadbeefcafe`" in body

    def test_none_line_count_renders_em_dash(self) -> None:
        files = [_record("settings.json", "settings", lines=None)]
        body = "\n".join(render_per_class_section(_inventory(files)))

        assert "| — |" in body

    def test_class_over_flat_limit_falls_back_to_aggregation(self) -> None:
        files = [
            _record(f"docs/sub/page{i}.md", "docs") for i in range(FLAT_TABLE_LIMIT + 1)
        ]
        body = "\n".join(render_per_class_section(_inventory(files)))

        assert "exceeds the per-class enumeration" in body
        assert "| subdirectory | file count |" in body
        # The shared subdir aggregates all pages.
        assert f"`docs/sub` | {FLAT_TABLE_LIMIT + 1:,}" in body


class TestRenderAggregatedSection:
    """Rendering the aggregated view of large classes.

    Covers aggregation by subdirectory and the omission of a large class that
    is absent from this inventory.
    """

    def test_aggregates_large_classes_by_subdir(self) -> None:
        files = [
            _record("memory/topic-a.md", "memory"),
            _record("memory/topic-b.md", "memory"),
            _record(".plans/suite/PHASE.md", "plan-artifact"),
        ]
        body = "\n".join(render_aggregated_section(_inventory(files)))

        assert "### memory (2)" in body
        assert "### plan-artifact (1)" in body

    def test_absent_large_class_is_omitted(self) -> None:
        body = "\n".join(
            render_aggregated_section(_inventory([_record("a.md", "docs")]))
        )

        assert "### memory" not in body
        assert "### plan-artifact" not in body


class TestRenderNarrativeSurfaceSection:
    """Rendering the narrative-surface index.

    Covers that only runtime behaviour surfaces are indexed, keeping the
    section scoped to what actually governs behaviour.
    """

    def test_indexes_only_runtime_behavior_surfaces(self) -> None:
        files = [
            _record("agents/a.md", "agent"),
            _record("rules/r.md", "rule"),  # not a narrative surface
            _record("commands/c.md", "command"),
        ]
        body = "\n".join(render_narrative_surface_section(_inventory(files)))

        assert "**Total surface files:** 2" in body
        assert "agents/a.md" in body
        assert "commands/c.md" in body
        assert "rules/r.md" not in body


class TestRenderPlanSuitesSection:
    """Rendering the plan-suite section.

    Covers the empty case rendering nothing, enumeration of suites with their
    counts and root files, the skipping of a degenerate plan path that names no
    suite, and the suite whose files are all deep enough that no root sub-table
    is emitted.
    """

    def test_no_plan_files_renders_nothing(self) -> None:
        assert render_plan_suites_section(_inventory([_record("a.md", "docs")])) == []

    def test_enumerates_suites_with_counts_and_root_files(self) -> None:
        files = [
            _record(".plans/alpha/PROGRESS.md", "plan-artifact", size=500),
            _record(".plans/alpha/phases/01/PHASE.md", "plan-artifact", size=300),
            _record(".plans/beta/MASTER-PLAN.md", "plan-artifact", size=200),
        ]
        body = "\n".join(render_plan_suites_section(_inventory(files)))

        assert "**Total plan suites:** 2" in body
        assert "**Total plan files:** 3" in body
        # Suite row records file count and summed bytes.
        assert "`alpha` | 2 | 800" in body
        # Root-file sub-table lists the depth-3 file, not the deep phase file.
        assert "Suite `alpha` — root files" in body
        assert "PROGRESS.md" in body
        assert "phases/01/PHASE.md" not in body

    def test_degenerate_plan_path_without_suite_is_skipped(self) -> None:
        # A plan-artifact path with no suite segment (no '/') is ignored for
        # the per-suite grouping but still counts toward the plan-file total.
        files = [
            _record("orphan-plan.md", "plan-artifact"),
            _record(".plans/alpha/PROGRESS.md", "plan-artifact"),
        ]
        body = "\n".join(render_plan_suites_section(_inventory(files)))

        assert "**Total plan suites:** 1" in body
        assert "**Total plan files:** 2" in body

    def test_suite_with_only_deep_files_emits_no_root_subtable(self) -> None:
        # Every file is below the suite root -> no depth-3 root file -> the
        # per-suite root sub-table is skipped for that suite.
        files = [_record(".plans/gamma/phases/01/PHASE.md", "plan-artifact")]
        body = "\n".join(render_plan_suites_section(_inventory(files)))

        assert "`gamma` | 1 |" in body
        assert "Suite `gamma` — root files" not in body


class TestRenderSkippedSection:
    """Rendering the skipped-directory list.

    Covers that each skipped directory is listed, so an omission from the scan
    is visible rather than silent.
    """

    def test_lists_each_skipped_directory(self) -> None:
        body = "\n".join(
            render_skipped_section(
                _inventory([_record("a.md", "docs")], skipped=["dist", "node_modules"])
            )
        )

        assert "_2 directories were skipped during the walk._" in body
        assert "- `dist`" in body
        assert "- `node_modules`" in body


class TestRenderInventory:
    """Composing the whole document.

    Covers that every section is emitted in its declared order.
    """

    def test_composes_every_section_in_order(self) -> None:
        files = [
            _record("agents/a.md", "agent"),
            _record("memory/m.md", "memory"),
            _record(".plans/s/PROGRESS.md", "plan-artifact"),
        ]
        body = render_inventory(_inventory(files, skipped=["dist"]))

        # Section headers appear in document order.
        order = [
            "# Inventory",
            "## Aggregate stats",
            "## Files by class (enumerated)",
            "## Files by class (aggregated)",
            "## Narrative-surface index",
            "## Plan-artifact recursive inventory",
            "## Appendix — skipped directories",
        ]
        positions = [body.index(h) for h in order]
        assert positions == sorted(positions)


class TestParseArguments:
    """Command-line argument parsing.

    Covers that both the inventory and the output path are required.
    """

    def test_requires_inventory_and_output(self) -> None:
        args = parse_arguments(["--inventory", "i.json", "--output", "o.md"])
        assert args.inventory == Path("i.json")
        assert args.output == Path("o.md")


class TestMain:
    """Process-level entry point behaviour.

    Covers the error exit on a missing inventory against the success path that
    writes the Markdown mirror.
    """

    def test_missing_inventory_returns_error(self, tmp_path: Path) -> None:
        code = main(
            [
                "--inventory",
                str(tmp_path / "absent.json"),
                "--output",
                str(tmp_path / "o.md"),
            ]
        )
        assert code == EXIT_ERROR

    def test_writes_the_markdown_mirror_and_returns_ok(self, tmp_path: Path) -> None:
        inv_path = tmp_path / "inv.json"
        out = tmp_path / "nested" / "inventory.md"
        inv_path.write_text(
            json.dumps(_inventory([_record("agents/a.md", "agent")])),
            encoding="utf-8",
        )

        code = main(["--inventory", str(inv_path), "--output", str(out)])

        assert code == EXIT_OK
        assert out.is_file()
        assert "# Inventory" in out.read_text(encoding="utf-8")
