# SPDX-License-Identifier: MIT

"""Emit a human-readable Markdown mirror of inventory.json.

Why this renderer exists. The machine-readable inventory drives every
downstream tool, but humans audit the working tree by reading prose.
This renderer produces ``inventory.md`` so the operator can answer
questions like "what scaffolding files do we ship?" or "which agents
exist?" without parsing JSON.

Output structure. The Markdown carries five sections: aggregate stats
(file count, class distribution, header-status distribution, header-
variant distribution); per-class file tables for the small classes
(agents, commands, skills, hooks, output-styles, statuslines, settings,
MCP, scaffolding, docs) — each row records path, line-count, SHA-256
prefix, and header-status; aggregated views for the large classes
(memory, plan-artifact) since per-file enumeration in the thousands
is unreadable; a narrative-surface index listing every file that
influences agent behavior at runtime; and a plan-suite recursive
sub-section enumerating every suite under ``.plans/`` with per-suite
file counts.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# Classes whose populations are small enough to enumerate row-by-row in
# the per-class tables. Larger classes get aggregated views instead.
ENUMERATED_CLASSES: Final[tuple[str, ...]] = (
    "agent",
    "command",
    "skill",
    "hook",
    "output-style",
    "statusline",
    "settings",
    "mcp",
    "scaffolding",
    "docs",
)

# Threshold above which a class is summarized by directory rather than
# enumerated as a flat table.
FLAT_TABLE_LIMIT: Final[int] = 200

# Narrative-surface classes — files that influence agent behavior at
# runtime. The ecosystem-audit skill sweeps these surfaces; the index
# below mirrors that scope.
NARRATIVE_SURFACE_CLASSES: Final[tuple[str, ...]] = (
    "agent",
    "command",
    "skill",
    "hook",
    "output-style",
    "docs",
)

# Sub-keys of the inventory to read.
KEY_FILES: Final[str] = "files"
KEY_BY_CLASS: Final[str] = "by-class"
KEY_BY_HEADER_STATUS: Final[str] = "by-header-status"
KEY_BY_HEADER_VARIANT: Final[str] = "by-header-variant"
KEY_TOTAL: Final[str] = "total-files"
KEY_SKIPPED: Final[str] = "skipped-directories"
KEY_GENERATED: Final[str] = "generated-at"
KEY_ROOT: Final[str] = "root"

EXIT_OK: Final[int] = 0
EXIT_ERROR: Final[int] = 1


def load_inventory(path: Path) -> dict[str, object]:
    """Read inventory.json and return its parsed payload."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _format_int(value: int) -> str:
    """Pretty-print an integer with thousand separators."""
    return f"{value:,}"


def render_aggregate_section(inventory: dict[str, object]) -> list[str]:
    """Emit the aggregate-stats section."""
    lines = [
        "## Aggregate stats",
        "",
        f"**Root:** `{inventory[KEY_ROOT]}`",
        f"**Generated at:** {inventory[KEY_GENERATED]}",
        f"**Total files:** {_format_int(inventory[KEY_TOTAL])}",
        f"**Skipped directories:** {len(inventory[KEY_SKIPPED])}",
        "",
        "### By class",
        "",
        "| class | count |",
        "|-------|------:|",
    ]
    by_class = inventory[KEY_BY_CLASS]
    for cls in sorted(by_class, key=lambda k: -by_class[k]):
        if by_class[cls] == 0:
            continue
        lines.append(f"| `{cls}` | {_format_int(by_class[cls])} |")
    lines.append("")

    lines.extend(
        [
            "### By header status",
            "",
            "| status | count |",
            "|--------|------:|",
        ]
    )
    by_hs = inventory[KEY_BY_HEADER_STATUS]
    for hs in sorted(by_hs, key=lambda k: -by_hs[k]):
        if by_hs[hs] == 0:
            continue
        lines.append(f"| `{hs}` | {_format_int(by_hs[hs])} |")
    lines.append("")

    lines.extend(
        [
            "### By header variant",
            "",
            "| variant | count |",
            "|---------|------:|",
        ]
    )
    by_hv = inventory[KEY_BY_HEADER_VARIANT]
    for hv in sorted(by_hv, key=lambda k: -by_hv[k]):
        if by_hv[hv] == 0:
            continue
        lines.append(f"| `{hv}` | {_format_int(by_hv[hv])} |")
    lines.append("")

    return lines


def render_per_class_section(inventory: dict[str, object]) -> list[str]:
    """Emit per-class file tables for the enumerated classes."""
    files = inventory[KEY_FILES]
    by_cls: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in files:
        by_cls[record["class"]].append(record)

    lines = ["## Files by class (enumerated)", ""]
    for cls in ENUMERATED_CLASSES:
        records = sorted(by_cls.get(cls, []), key=lambda r: r["path"])
        if not records:
            continue

        lines.append(f"### {cls} ({len(records)})")
        lines.append("")
        if len(records) > FLAT_TABLE_LIMIT:
            lines.append(
                f"_Class population exceeds the per-class enumeration "
                f"limit ({FLAT_TABLE_LIMIT}); see aggregated view below._"
            )
            lines.extend(_render_aggregated_subdirs(records))
            continue

        lines.append("| path | lines | sha256 | header-status |")
        lines.append("|------|------:|--------|---------------|")
        for record in records:
            line_count = record["line-count"]
            line_str = _format_int(line_count) if line_count is not None else "—"
            sha_short = str(record["sha256"])[:12]
            lines.append(
                f"| `{record['path']}` | {line_str} | `{sha_short}` | "
                f"`{record['header-status']}` |"
            )
        lines.append("")

    return lines


def _render_aggregated_subdirs(records: list[dict[str, object]]) -> list[str]:
    """Aggregate a large class by top-level subdirectory."""
    by_subdir: defaultdict[str, int] = defaultdict(int)
    for record in records:
        parts = record["path"].split("/")
        subdir = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
        by_subdir[subdir] += 1

    lines = [
        "",
        "| subdirectory | file count |",
        "|--------------|-----------:|",
    ]
    for subdir in sorted(by_subdir, key=lambda s: -by_subdir[s]):
        lines.append(f"| `{subdir}` | {_format_int(by_subdir[subdir])} |")
    lines.append("")
    return lines


def render_aggregated_section(inventory: dict[str, object]) -> list[str]:
    """Emit aggregated views for large classes (memory, plan-artifact)."""
    files = inventory[KEY_FILES]
    by_cls: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in files:
        by_cls[record["class"]].append(record)

    lines = ["## Files by class (aggregated)", ""]
    for cls in ("memory", "plan-artifact", "unknown"):
        records = by_cls.get(cls, [])
        if not records:
            continue

        lines.append(f"### {cls} ({len(records)})")
        lines.extend(_render_aggregated_subdirs(records))

    return lines


def render_narrative_surface_section(inventory: dict[str, object]) -> list[str]:
    """Emit the narrative-surface index."""
    files = inventory[KEY_FILES]
    surfaces = [r for r in files if r["class"] in NARRATIVE_SURFACE_CLASSES]
    surfaces.sort(key=lambda r: (r["class"], r["path"]))

    lines = [
        "## Narrative-surface index",
        "",
        " ".join(
            (
                "Every file in the corpus that influences agent behavior at",
                "runtime — agent system prompts, command bodies, skill entry",
                "points, hook messages, output-styles, and behavioral rules.",
                "The ecosystem-audit skill sweeps this surface set when",
                "checking convention coherence.",
            )
        ),
        "",
        f"**Total surface files:** {len(surfaces)}",
        "",
        "| class | path | lines |",
        "|-------|------|------:|",
    ]
    for record in surfaces:
        line_count = record["line-count"]
        line_str = _format_int(line_count) if line_count is not None else "—"
        lines.append(f"| `{record['class']}` | `{record['path']}` | {line_str} |")
    lines.append("")

    return lines


def render_plan_suites_section(inventory: dict[str, object]) -> list[str]:
    """Emit the recursive plan-artifact sub-section.

    The recursive structure of ``.plans/`` hosts one subdirectory per
    plan suite. Per suite, this section emits the suite name, total
    file count, total bytes, and a per-suite-root file list (the
    top-level Markdown documents at each suite's root directory, not
    the deep nested-folder tree which is enumerated only in aggregate).
    """
    files = inventory[KEY_FILES]
    plan_files = [r for r in files if r["class"] == "plan-artifact"]
    if not plan_files:
        return []

    by_suite: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for record in plan_files:
        parts = record["path"].split("/")
        if len(parts) < 2:
            continue
        suite_name = parts[1]
        by_suite[suite_name].append(record)

    lines = [
        "## Plan-artifact recursive inventory",
        "",
        " ".join(
            (
                "Every plan suite under `.plans/` is enumerated below. The plan",
                "suites are project-local working memory — they live on disk",
                "but are excluded from the published tree by the suite",
                "gitignore. Per suite, the table records suite name, total",
                "file count, and total bytes; the per-suite root files appear",
                "in the sub-table that follows.",
            )
        ),
        "",
        f"**Total plan suites:** {len(by_suite)}",
        f"**Total plan files:** {_format_int(len(plan_files))}",
        "",
        "| suite | files | bytes |",
        "|-------|------:|------:|",
    ]
    suite_names = sorted(by_suite)
    for suite in suite_names:
        records = by_suite[suite]
        total_bytes = sum(r["size"] for r in records)
        lines.append(
            f"| `{suite}` | {_format_int(len(records))} | {_format_int(total_bytes)} |"
        )
    lines.append("")

    for suite in suite_names:
        records = by_suite[suite]
        root_files = [
            r
            for r in records
            if len(r["path"].split("/")) == 3  # .plans/<suite>/<file>
        ]
        if not root_files:
            continue
        root_files.sort(key=lambda r: r["path"])
        lines.append(f"### Suite `{suite}` — root files")
        lines.append("")
        lines.append("| path | lines | sha256 |")
        lines.append("|------|------:|--------|")
        for record in root_files:
            line_count = record["line-count"]
            line_str = _format_int(line_count) if line_count is not None else "—"
            sha_short = str(record["sha256"])[:12]
            rel_path = record["path"].split("/", 2)[-1]
            lines.append(f"| `{rel_path}` | {line_str} | `{sha_short}` |")
        lines.append("")

    return lines


def render_skipped_section(inventory: dict[str, object]) -> list[str]:
    """Emit the skipped-directories list as an appendix."""
    skipped = inventory[KEY_SKIPPED]
    lines = [
        "## Appendix — skipped directories",
        "",
        f"_{len(skipped)} directories were skipped during the walk._",
        "",
    ]
    for directory in skipped:
        lines.append(f"- `{directory}`")
    lines.append("")
    return lines


def render_inventory(inventory: dict[str, object]) -> str:
    """Compose the complete Markdown document from the inventory payload."""
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    lines: list[str] = [
        "# Inventory",
        "",
        f"_Rendered at {timestamp} from `inventory.json`._",
        "",
    ]
    lines.extend(render_aggregate_section(inventory))
    lines.extend(render_per_class_section(inventory))
    lines.extend(render_aggregated_section(inventory))
    lines.extend(render_narrative_surface_section(inventory))
    lines.extend(render_plan_suites_section(inventory))
    lines.extend(render_skipped_section(inventory))
    return "\n".join(lines) + "\n"


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """CLI surface — inventory and output are required."""
    parser = argparse.ArgumentParser(
        prog="render_inventory",
        description="Emit a human-readable Markdown mirror of inventory.json.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        required=True,
        help="Inventory JSON path produced by build_inventory.py.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output Markdown path (e.g., .audit/inventory.md).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Entry point — returns the exit code."""
    args = parse_arguments(argv)
    inventory_path = args.inventory.resolve()
    output = args.output.resolve()

    if not inventory_path.is_file():
        print(f"error: inventory not found: {inventory_path}", file=sys.stderr)
        return EXIT_ERROR

    inventory = load_inventory(inventory_path)
    body = render_inventory(inventory)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(body, encoding="utf-8")

    print(f"render-inventory: lines={body.count(chr(10))}; output={output}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
