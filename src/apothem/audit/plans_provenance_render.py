# SPDX-License-Identifier: MIT

"""Why this module exists — turning resolved records into documents.

The provenance pipeline ends with two artifacts: a JSON envelope the
migration-confirmation pass reads, and a markdown mirror an operator reads.
Both are built from the same resolved records, and neither decision about
*what* a record says belongs here — by the time these functions run, every
verdict is settled.

Scope. Presentation only. The one judgement this module does make is about
escaping: values interpolated into a markdown table cell have their pipes
escaped, because an unescaped pipe silently splits the row.

Both emitters create their own output directory. The documents land under a
generated-state tree that a clean checkout does not carry, so requiring the
caller to have made it first would only move the same ``mkdir`` upstream.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apothem.audit.plans_provenance_model import ProvenanceRecord, SuiteVerdict
from apothem.audit.plans_provenance_vocabulary import (
    ALL_CONFIDENCES,
    CONFIDENCE_RECURSIVE_SELF,
    CONFIDENCE_UNMAPPABLE,
)

__all__ = [
    "emit_json",
    "emit_markdown",
    "record_to_dict",
]


def emit_json(
    records: list[ProvenanceRecord],
    suite_verdicts: dict[str, SuiteVerdict],
    inventory_sha: str,
    out: Path,
) -> None:
    by_suite_block: dict[str, dict[str, Any]] = {}
    for suite, verdict in sorted(suite_verdicts.items()):
        by_suite_block[suite] = {
            "file-count": verdict.file_count,
            "destination": verdict.destination,
            "confidence": verdict.confidence,
            "rationale": verdict.rationale,
            "aggregate-repo-urls": verdict.aggregate_repo_urls,
            "aggregate-abs-paths": verdict.aggregate_abs_paths,
            "eco-signal-density": round(verdict.eco_signal_density, 3),
        }
    by_confidence_total: dict[str, int] = dict.fromkeys(ALL_CONFIDENCES, 0)
    for r in records:
        by_confidence_total[r.confidence] += 1
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "scanner": "build_plans_provenance",
        "inventory-source-sha256": inventory_sha,
        "suite-count": len(suite_verdicts),
        "file-count": len(records),
        "by-confidence": by_confidence_total,
        "suites": by_suite_block,
        "files": [record_to_dict(r) for r in records],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def record_to_dict(r: ProvenanceRecord) -> dict[str, Any]:
    return {
        "path": r.path,
        "suite": r.suite,
        "mtime": r.mtime,
        "sha256": r.sha256,
        "line-count": r.line_count,
        "frontmatter-project": r.frontmatter_project,
        "signals": asdict(r.signals),
        "inferred-destination": r.inferred_destination,
        "confidence": r.confidence,
        "proposed-destination-filename": r.proposed_destination_filename,
        "notes": r.notes,
    }


def emit_markdown(
    records: list[ProvenanceRecord],
    suite_verdicts: dict[str, SuiteVerdict],
    out: Path,
) -> None:
    total = len(records)
    by_confidence: dict[str, int] = dict.fromkeys(ALL_CONFIDENCES, 0)
    for r in records:
        by_confidence[r.confidence] += 1
    orphans = [r for r in records if r.confidence == CONFIDENCE_UNMAPPABLE]

    lines: list[str] = []
    lines.append("# Plans Provenance — Per-Suite, Per-File Map")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## Aggregate Stats")
    lines.append("")
    lines.append(f"- **Total suites:** {len(suite_verdicts)}")
    lines.append(f"- **Total plan files:** {total}")
    lines.append("- **By confidence:**")
    for c in ALL_CONFIDENCES:
        lines.append(f"  - `{c}`: {by_confidence[c]}")
    lines.append("")

    lines.append("## Suite-Level Verdicts")
    lines.append("")
    lines.append("| Suite | Files | Confidence | Destination |")
    lines.append("|-------|-------|------------|-------------|")
    for suite, verdict in sorted(suite_verdicts.items()):
        suite_disp = suite.replace("|", "\\|")
        dest_disp = verdict.destination.replace("|", "\\|")
        lines.append(
            f"| `{suite_disp}` | {verdict.file_count} |"
            f" `{verdict.confidence}` | {dest_disp} |"
        )
    lines.append("")

    lines.append("## Per-Suite Tables")
    lines.append("")
    by_suite: dict[str, list[ProvenanceRecord]] = {}
    for r in records:
        by_suite.setdefault(r.suite or "<root>", []).append(r)
    for suite in sorted(by_suite):
        suite_records = sorted(by_suite[suite], key=lambda r: r.path)
        suite_verdict = suite_verdicts.get(suite)
        lines.append(f"### `{suite}`")
        lines.append("")
        if suite_verdict is not None:
            lines.append(
                f"_Confidence: `{suite_verdict.confidence}`. Destination:"
                f" {suite_verdict.destination}._"
            )
            lines.append("")
            lines.append("**Rationale:**")
            lines.append("")
            for fragment in suite_verdict.rationale:
                lines.append(f"- {fragment}")
            lines.append("")
        lines.append("| Path | Proposed filename |")
        lines.append("|------|-------------------|")
        for r in suite_records:
            path_disp = r.path.replace("|", "\\|")
            file_disp = r.proposed_destination_filename.replace("|", "\\|")
            lines.append(f"| `{path_disp}` | `{file_disp}` |")
        lines.append("")

    lines.append("## Recursive-Case Annotation")
    lines.append("")
    recursive = [
        v for v in suite_verdicts.values() if v.confidence == CONFIDENCE_RECURSIVE_SELF
    ]
    if recursive:
        v = recursive[0]
        lines.append(
            f"The suite `{v.suite}` describes the very ecosystem it"
            f" lives in ({v.file_count} files); the migration leaves"
            " it in place and the cleanup phase adds `.plans/` to the"
            " repository's `.gitignore` so the directory carries no"
            " plan-product through publication."
        )
    else:
        lines.append("_No recursive-self records._")
    lines.append("")

    lines.append("## Orphan Candidates")
    lines.append("")
    if orphans:
        lines.append(
            f"{len(orphans)} file(s) with `confidence: unmappable`."
            " The migration-confirmation pass routes these to the"
            " operator for explicit disposition."
        )
        lines.append("")
        for r in sorted(orphans, key=lambda r: r.path):
            lines.append(f"- `{r.path}`")
    else:
        lines.append("_No orphan candidates surfaced._")
    lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
