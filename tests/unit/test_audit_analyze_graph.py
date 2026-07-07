# SPDX-License-Identifier: MIT

"""Unit tests for the capability-graph health analyzer.

``apothem.audit.analyze_graph`` surfaces two health signals from the
capability graph the builder emits: orphan nodes (zero inbound edges) and
dangling references (edges to unregistered targets). Its detection and
rendering functions are pure transforms over the graph payload, so they are
covered directly here — the consumer path (``main``) is exercised end-to-end
through a synthetic graph fixture written to ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apothem.audit.analyze_graph import (
    EXIT_ERROR,
    EXIT_OK,
    KIND_HARNESS_EVENT,
    KIND_HOOK,
    detect_dangling,
    detect_orphans,
    load_graph,
    main,
    parse_arguments,
    render_dangling_report,
    render_orphans_report,
)


def _graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    """Assemble a graph payload with a consistent ``edge-count``."""
    return {"nodes": nodes, "edges": edges, "edge-count": len(edges)}


class TestLoadGraph:
    def test_round_trips_the_json_payload(self, tmp_path: Path) -> None:
        path = tmp_path / "graph.json"
        payload = _graph(
            [{"id": "a", "kind": "rule", "path": "a.md"}],
            [],
        )
        path.write_text(json.dumps(payload), encoding="utf-8")

        assert load_graph(path) == payload


class TestDetectOrphans:
    def test_node_with_no_inbound_edge_is_orphan(self) -> None:
        graph = _graph(
            [
                {"id": "rule-a", "kind": "rule", "path": "a.md"},
                {"id": "skill-b", "kind": "skill", "path": "b.md"},
            ],
            [{"source": "rule-a", "target": "skill-b", "relation": "references"}],
        )

        orphans = detect_orphans(graph)

        # skill-b has an inbound edge; rule-a has none -> rule-a is the orphan.
        assert orphans == {"rule": [{"id": "rule-a", "kind": "rule", "path": "a.md"}]}

    def test_harness_event_nodes_are_excluded(self) -> None:
        graph = _graph(
            [
                {"id": "evt", "kind": KIND_HARNESS_EVENT, "path": ""},
                {"id": "rule-a", "kind": "rule", "path": "a.md"},
            ],
            [],
        )

        orphans = detect_orphans(graph)

        # The event node, despite zero inbound edges, is never reported.
        assert KIND_HARNESS_EVENT not in orphans
        assert orphans == {"rule": [{"id": "rule-a", "kind": "rule", "path": "a.md"}]}

    def test_hook_bound_to_an_event_is_not_orphan(self) -> None:
        # A hook participates by sourcing a binds-to edge to the event it
        # serves; it carries no inbound edge yet is not an orphan — its
        # consumer is the event, reached through the outbound binds-to edge.
        hook = {
            "id": "hooks/messages/stop.md",
            "kind": KIND_HOOK,
            "path": "hooks/messages/stop.md",
        }
        graph = _graph(
            [{"id": "Stop", "kind": KIND_HARNESS_EVENT, "path": ""}, hook],
            [{"source": hook["id"], "target": "Stop", "relation": "binds-to"}],
        )

        # The bound hook (outbound binds-to, zero inbound) is excluded.
        assert detect_orphans(graph) == {}

    def test_unbound_hook_with_no_inbound_edge_is_orphan(self) -> None:
        # A hook bound to no event and referenced by nothing is a genuine
        # Refine/Remove candidate — the signal the report is meant to surface.
        hook = {
            "id": "hooks/messages/dead.md",
            "kind": KIND_HOOK,
            "path": "hooks/messages/dead.md",
        }
        graph = _graph(
            [{"id": "Stop", "kind": KIND_HARNESS_EVENT, "path": ""}, hook],
            [],
        )

        assert detect_orphans(graph) == {"hook": [hook]}

    def test_fully_connected_graph_has_no_orphans(self) -> None:
        graph = _graph(
            [
                {"id": "a", "kind": "rule", "path": "a.md"},
                {"id": "b", "kind": "skill", "path": "b.md"},
            ],
            [
                {"source": "a", "target": "b", "relation": "references"},
                {"source": "b", "target": "a", "relation": "cited-by"},
            ],
        )

        assert detect_orphans(graph) == {}


class TestDetectDangling:
    def test_edge_to_unregistered_target_is_dangling(self) -> None:
        graph = _graph(
            [{"id": "a", "kind": "rule", "path": "a.md"}],
            [
                {"source": "a", "target": "ghost", "relation": "references"},
                {"source": "a", "target": "a", "relation": "self"},
            ],
        )

        dangling = detect_dangling(graph)

        assert len(dangling) == 1
        assert dangling[0]["target"] == "ghost"

    def test_well_formed_graph_has_no_dangling(self) -> None:
        graph = _graph(
            [
                {"id": "a", "kind": "rule", "path": "a.md"},
                {"id": "b", "kind": "skill", "path": "b.md"},
            ],
            [{"source": "a", "target": "b", "relation": "references"}],
        )

        assert detect_dangling(graph) == []


class TestRenderOrphansReport:
    def test_zero_orphans_renders_the_clean_marker(self) -> None:
        graph = _graph([{"id": "a", "kind": "rule", "path": "a.md"}], [])
        report = render_orphans_report({}, graph)

        assert "# Orphan nodes" in report
        assert "_No orphans detected._" in report

    def test_grouped_report_lists_each_orphan_sorted(self) -> None:
        graph = _graph(
            [
                {"id": "z-rule", "kind": "rule", "path": "z.md"},
                {"id": "a-rule", "kind": "rule", "path": ""},
            ],
            [],
        )
        orphans = detect_orphans(graph)

        report = render_orphans_report(orphans, graph)

        assert "## rule (2)" in report
        # Sorted by id -> a-rule precedes z-rule.
        assert report.index("a-rule") < report.index("z-rule")
        # An empty path renders the explicit no-source-path marker.
        assert "_(no source path)_" in report
        # The orphan-rate line reflects 2 of 2 eligible nodes.
        assert "2 / 2" in report


class TestRenderDanglingReport:
    def test_zero_dangling_renders_the_clean_marker(self) -> None:
        graph = _graph([{"id": "a", "kind": "rule", "path": "a.md"}], [])
        report = render_dangling_report([], graph)

        assert "# Dangling references" in report
        assert "_No dangling references detected._" in report

    def test_grouped_report_lists_each_dangling_edge_by_relation(self) -> None:
        graph = _graph(
            [{"id": "a", "kind": "rule", "path": "a.md"}],
            [{"source": "a", "target": "ghost", "relation": "references"}],
        )
        dangling = detect_dangling(graph)

        report = render_dangling_report(dangling, graph)

        assert "## references (1)" in report
        assert "`a`" in report
        assert "`ghost`" in report

    def test_evidence_path_accepts_either_key_spelling(self) -> None:
        graph = _graph(
            [{"id": "a", "kind": "rule", "path": "a.md"}],
            [
                {
                    "source": "a",
                    "target": "ghost",
                    "relation": "references",
                    "evidence_path": "a.md:5",
                }
            ],
        )
        report = render_dangling_report(detect_dangling(graph), graph)

        # The underscore spelling resolves when the hyphen spelling is absent.
        assert "a.md:5" in report


class TestParseArguments:
    def test_requires_graph_and_both_outputs(self) -> None:
        args = parse_arguments(
            [
                "--graph",
                "g.json",
                "--orphans-output",
                "o.md",
                "--dangling-output",
                "d.md",
            ]
        )

        assert args.graph == Path("g.json")
        assert args.orphans_output == Path("o.md")
        assert args.dangling_output == Path("d.md")


class TestMain:
    def test_missing_graph_returns_error(self, tmp_path: Path) -> None:
        code = main(
            [
                "--graph",
                str(tmp_path / "absent.json"),
                "--orphans-output",
                str(tmp_path / "o.md"),
                "--dangling-output",
                str(tmp_path / "d.md"),
            ]
        )

        assert code == EXIT_ERROR

    def test_writes_both_reports_and_returns_ok(self, tmp_path: Path) -> None:
        graph_path = tmp_path / "graph.json"
        orphans_out = tmp_path / "nested" / "orphans.md"
        dangling_out = tmp_path / "nested" / "dangling.md"
        graph_path.write_text(
            json.dumps(
                _graph(
                    [
                        {"id": "a", "kind": "rule", "path": "a.md"},
                        {"id": "b", "kind": "skill", "path": "b.md"},
                    ],
                    [{"source": "a", "target": "b", "relation": "references"}],
                )
            ),
            encoding="utf-8",
        )

        code = main(
            [
                "--graph",
                str(graph_path),
                "--orphans-output",
                str(orphans_out),
                "--dangling-output",
                str(dangling_out),
            ]
        )

        assert code == EXIT_OK
        # Parent directories are created on demand.
        assert orphans_out.is_file()
        assert dangling_out.is_file()
        # 'a' has no inbound edge -> reported as the one orphan.
        assert "## rule (1)" in orphans_out.read_text(encoding="utf-8")
        assert "_No dangling references detected._" in dangling_out.read_text(
            encoding="utf-8"
        )
