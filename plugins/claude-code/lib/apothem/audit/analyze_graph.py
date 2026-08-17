# SPDX-License-Identifier: MIT

"""Detect orphan nodes and dangling references in the capability graph.

Why this analysis exists. The capability-graph builder records every
observed cross-artifact reference, but it cannot distinguish a healthy
node-count from an unhealthy one. Two specific health signals are
worth surfacing before the next audit phase classifies each artifact:

* **Orphan nodes** — addressable units with zero inbound edges. An
  orphan is a candidate for ``Refine`` or ``Remove`` at the next
  classification pass. A persistent agent with no commands invoking
  it; a skill with no rule referencing it; an output-style that no
  routing decision targets — each is detectable here without
  re-walking the source.
* **Dangling references** — edges whose target node is not registered.
  In a well-formed graph these are zero by construction (the builder
  only emits edges to registered targets). A non-zero count would
  indicate either a builder bug or an inventory / graph mismatch.

Both signals emit human-readable Markdown reports for operator review.
The orphan report groups by node-kind; the dangling report groups by
relation-type. Orphan harness events are excluded from the report
(they are virtual nodes whose inbound edges are the population of
hook bindings — an event with zero inbound edges merely means no hook
is bound to it, which is information for the audit but not a defect).
Hooks bound to a harness event are excluded for the dual reason: a
hook is not pointed at, it is executed by the engine when its bound
event fires, so its consumer is the event it serves — reached through
an outbound binds-to edge, never an inbound reference.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

KIND_HARNESS_EVENT: Final[str] = "harness-event"
KIND_HOOK: Final[str] = "hook"
RELATION_BINDS_TO: Final[str] = "binds-to"

EXIT_OK: Final[int] = 0
EXIT_ERROR: Final[int] = 1


def load_graph(path: Path) -> dict[str, object]:
    """Read capability-graph.json and return its parsed payload."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def detect_orphans(graph: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    """Return a mapping from node-kind to the list of orphan node records.

    A node is orphan when its identifier appears in zero edge ``target``
    fields, with two participation exclusions:

    * Harness-event virtual nodes — an event with no inbound binds-to edge
      is a configuration observation (no hook bound to it), not a defect.
    * Hooks that source a ``binds-to`` edge — a hook is executed by the
      engine when its bound event fires, so its consumer is the event it
      serves, reached through an *outbound* binds-to edge rather than an
      inbound reference. A bound hook is a participant, not an orphan,
      even when nothing references it by name.
    """
    inbound: defaultdict[str, int] = defaultdict(int)
    bound_hooks: set[str] = set()
    for edge in graph["edges"]:
        inbound[edge["target"]] += 1
        if edge["relation"] == RELATION_BINDS_TO:
            bound_hooks.add(edge["source"])

    orphans_by_kind: dict[str, list[dict[str, object]]] = defaultdict(list)
    for node in graph["nodes"]:
        if node["kind"] == KIND_HARNESS_EVENT:
            continue
        if node["kind"] == KIND_HOOK and node["id"] in bound_hooks:
            continue
        if inbound.get(node["id"], 0) == 0:
            orphans_by_kind[node["kind"]].append(node)

    return dict(orphans_by_kind)


def detect_dangling(graph: dict[str, object]) -> list[dict[str, object]]:
    """Return the list of edges whose target is not a registered node id."""
    registered = {n["id"] for n in graph["nodes"]}
    dangling: list[dict[str, object]] = []
    for edge in graph["edges"]:
        if edge["target"] not in registered:
            dangling.append(edge)
    return dangling


def render_orphans_report(
    orphans_by_kind: dict[str, list[dict[str, object]]],
    graph: dict[str, object],
) -> str:
    """Render the orphan report as Markdown grouped by node-kind."""
    total_orphans = sum(len(v) for v in orphans_by_kind.values())
    total_eligible = sum(1 for n in graph["nodes"] if n["kind"] != KIND_HARNESS_EVENT)
    rate = (total_orphans / total_eligible * 100) if total_eligible else 0
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    lines: list[str] = [
        "# Orphan nodes",
        "",
        f"_Generated at {timestamp}._",
        "",
        " ".join(
            (
                "An orphan is an addressable unit (agent, command, skill, hook,",
                "output-style, statusline, rule, MCP manifest) with zero inbound",
                "edges in the capability graph. Orphan presence is a candidate",
                "for the next audit phase to verdict as `Refine` (rebind to its",
                "intended consumer) or `Remove` (no consumer ever materializes).",
            )
        ),
        "",
        f"**Total orphans:** {total_orphans} / {total_eligible} "
        f"non-event nodes ({rate:.1f}%).",
        "",
    ]

    if total_orphans == 0:
        lines.append("_No orphans detected._")
        return "\n".join(lines) + "\n"

    for kind in sorted(orphans_by_kind):
        nodes = sorted(orphans_by_kind[kind], key=lambda n: n["id"])
        lines.append(f"## {kind} ({len(nodes)})")
        lines.append("")
        lines.append("| id | path |")
        lines.append("|----|------|")
        for node in nodes:
            path = node["path"] or "_(no source path)_"
            lines.append(f"| `{node['id']}` | `{path}` |")
        lines.append("")

    return "\n".join(lines) + "\n"


def render_dangling_report(
    dangling: list[dict[str, object]], graph: dict[str, object]
) -> str:
    """Render the dangling-reference report as Markdown grouped by relation."""
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    total_edges = graph["edge-count"]
    rate = (len(dangling) / total_edges * 100) if total_edges else 0

    lines: list[str] = [
        "# Dangling references",
        "",
        f"_Generated at {timestamp}._",
        "",
        " ".join(
            (
                "A dangling edge is a reference whose target identifier is not",
                "registered as a node in the capability graph. In a well-formed",
                "graph this is zero by construction. Non-zero counts indicate",
                "either a graph-builder defect or an inventory / graph mismatch",
                "that the next audit phase must reconcile.",
            )
        ),
        "",
        f"**Total dangling:** {len(dangling)} / {total_edges} edges ({rate:.1f}%).",
        "",
    ]

    if not dangling:
        lines.append("_No dangling references detected._")
        return "\n".join(lines) + "\n"

    by_relation: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for edge in dangling:
        by_relation[edge["relation"]].append(edge)

    for relation in sorted(by_relation):
        edges = by_relation[relation]
        lines.append(f"## {relation} ({len(edges)})")
        lines.append("")
        lines.append("| source | target | evidence |")
        lines.append("|--------|--------|----------|")
        for edge in edges:
            evidence = edge.get("evidence-path") or edge.get("evidence_path") or ""
            lines.append(f"| `{edge['source']}` | `{edge['target']}` | `{evidence}` |")
        lines.append("")

    return "\n".join(lines) + "\n"


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """CLI surface — graph input and two output paths are required."""
    parser = argparse.ArgumentParser(
        prog="analyze_graph",
        description="Detect orphans and dangling references in the capability graph.",
    )
    parser.add_argument(
        "--graph",
        type=Path,
        required=True,
        help="Capability-graph JSON path produced by build_capability_graph.py.",
    )
    parser.add_argument(
        "--orphans-output",
        type=Path,
        required=True,
        help="Output Markdown path for the orphan report (e.g., .audit/orphans.md).",
    )
    parser.add_argument(
        "--dangling-output",
        type=Path,
        required=True,
        help="Output Markdown path for the dangling-reference report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Entry point — returns the exit code."""
    args = parse_arguments(argv)
    graph_path = args.graph.resolve()
    orphans_output = args.orphans_output.resolve()
    dangling_output = args.dangling_output.resolve()

    if not graph_path.is_file():
        print(f"error: graph not found: {graph_path}", file=sys.stderr)
        return EXIT_ERROR

    graph = load_graph(graph_path)
    orphans_by_kind = detect_orphans(graph)
    dangling = detect_dangling(graph)

    orphans_output.parent.mkdir(parents=True, exist_ok=True)
    dangling_output.parent.mkdir(parents=True, exist_ok=True)

    orphans_output.write_text(
        render_orphans_report(orphans_by_kind, graph), encoding="utf-8"
    )
    dangling_output.write_text(
        render_dangling_report(dangling, graph), encoding="utf-8"
    )

    total_orphans = sum(len(v) for v in orphans_by_kind.values())
    print(
        f"graph-analysis: orphans={total_orphans} "
        f"({sum(1 for n in graph['nodes'] if n['kind'] != KIND_HARNESS_EVENT)} eligible); "
        f"dangling={len(dangling)} ({graph['edge-count']} edges); "
        f"orphans-report={orphans_output}; dangling-report={dangling_output}"
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
