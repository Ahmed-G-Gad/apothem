# SPDX-License-Identifier: MIT

"""Assign one classification verdict per inventory artifact.

Why this tool exists. The drift scans surface findings; the
classification matrix is the next-action layer that turns findings
into per-file verdicts. Every file in the inventory receives exactly
one verdict from the nine-verdict matrix — Keep, Refine, Rename,
Relocate, Merge, Split, Replace, Migrate-to-Project, Remove. The
verdict carries a one-line justification grounded in observed state
(a drift hit, an orphan classification, a header-status finding, a
class-rule directive) so the audit-gate consolidation can review
each verdict against its evidence.

What this tool consumes.

- ``.audit/inventory.json`` — the per-file metadata enumeration.
- ``.audit/drift-feature-refs.json`` / ``drift-stale-tokens.json`` /
  ``drift-broken-links.json`` / ``drift-frontmatter.json`` /
  ``drift-conflicting-directives.json`` / ``drift-secrets-pii.json`` /
  ``drift-plans-discipline.json`` / ``drift-ai-surfaces-coarse.json``
  — the eight per-scan finding documents from the drift scan family.
- ``.audit/orphans.md`` — the orphan classification from the
  capability-graph analysis.

What this tool emits.

- ``.audit/classification-matrix.md`` — a per-file Markdown table with
  the verdict, the evidence-class anchor, and a one-line justification.
- ``.audit/classification-matrix.json`` — the same data in machine-
  readable form for downstream consumers (the audit-gate consolidation,
  the per-class refit passes, the synthesis pass).

Verdict assignment rules apply in order; the first matching rule wins.
Plan-artifacts always receive ``Migrate-to-Project`` (deferred per-
suite confidence-scoring at the plans-provenance pass). Memory files
receive ``Keep`` (per-project state, not a refit target). For
narrative artifacts, the rule order is:

1. Genuine secret leak detected → ``Refine`` (rotate-and-remove)
2. HIGH-severity drift hits → ``Refine``
3. Orphan classification (no inbound capability-graph edge) AND no
   drift findings → ``Remove`` candidate (audit gate confirms)
4. Header-status absent on header-applicable file → ``Refine``
5. MEDIUM-severity drift hits → ``Refine``
6. LOW-severity drift hits only → ``Keep`` with ``has-watch-items``
   note
7. No drift, no orphan, header present or N/A → ``Keep``
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

VERDICTS: Final[list[str]] = [
    "Keep",
    "Refine",
    "Rename",
    "Relocate",
    "Merge",
    "Split",
    "Replace",
    "Migrate-to-Project",
    "Remove",
]

# The per-scan files this classifier consumes. The signal-name prefix
# helps the synthesis pass cite the right scan in the matrix's
# evidence column.
_SCAN_FILES: Final[list[tuple[str, str]]] = [
    ("scan_drift_features", ".audit/drift-feature-refs.json"),
    ("scan_stale_tokens", ".audit/drift-stale-tokens.json"),
    ("check_links", ".audit/drift-broken-links.json"),
    ("scan_frontmatter", ".audit/drift-frontmatter.json"),
    ("conflicting-directives", ".audit/drift-conflicting-directives.json"),
    ("scan_secrets_pii", ".audit/drift-secrets-pii.json"),
    ("scan_plans_discipline", ".audit/drift-plans-discipline.json"),
    ("scan_ai_surfaces_coarse", ".audit/drift-ai-surfaces-coarse.json"),
]


def _load_scan_findings(
    audit_dir: Path,
) -> dict[str, list[dict[str, Any]]]:
    """Aggregate every scan's hits keyed by source file path.

    The returned mapping is ``{file-path: [hit, ...]}`` where each hit
    carries its scanner-name in a ``scanner`` field for synthesis.
    """
    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scanner, rel_path in _SCAN_FILES:
        path = audit_dir / Path(rel_path).name
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for hit in payload.get("hits", []):
            file = hit.get("file", "")
            if not file:
                continue
            hit["scanner"] = scanner
            by_file[file].append(hit)
    return by_file


def _load_orphans(orphans_md: Path) -> set[str]:
    """Parse orphans.md for the set of orphan paths."""
    if not orphans_md.exists():
        return set()
    orphans: set[str] = set()
    # Each orphan row is: | `<id>` | `<path>` | — capture the second
    # backticked token per row.
    row_re = re.compile(r"^\|\s*`[^`]+`\s*\|\s*`([^`]+)`\s*\|")
    for line in orphans_md.read_text(encoding="utf-8").splitlines():
        match = row_re.match(line)
        if match:
            orphans.add(match.group(1))
    return orphans


def _max_severity(hits: list[dict[str, Any]]) -> str | None:
    """Return the highest severity present among ``hits``."""
    order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    best = 0
    best_sev: str | None = None
    for hit in hits:
        sev = hit.get("severity", "")
        rank = order.get(sev, 0)
        if rank > best:
            best = rank
            best_sev = sev
    return best_sev


def _is_genuine_secret(hits: list[dict[str, Any]]) -> bool:
    """Return True if a secret-candidate hit is present.

    The classifier consumes the content-root inventory (``src/apothem``),
    so test fixtures under ``tests/`` and the harness-managed
    ``.credentials.json`` — both outside the content root — never enter
    scope. The prior path-based exemptions for them could not fire under
    the content-root convention and have been removed; reinstate them if
    scope ever widens to a repo-root inventory.

    "Genuine" here selects the secret-candidate class the upstream scan already
    flagged — as opposed to a PII or absolute-path finding sharing the same
    scan — it does not independently re-validate the credential.
    """
    return any(hit.get("signal", "").startswith("secret-candidate") for hit in hits)


def _classify_record(
    record: dict[str, Any],
    hits: list[dict[str, Any]],
    orphans: set[str],
) -> tuple[str, str, list[str]]:
    """Return ``(verdict, justification, evidence-anchors)`` per the
    nine-verdict classification matrix."""
    cls = record.get("class", "")
    rel = record.get("path", "")
    anchors: list[str] = []
    # Plan-artifacts: matrix-mandated automatic verdict.
    if cls == "plan-artifact":
        return (
            "Migrate-to-Project",
            "Plan-artifact under the project-local plans tree"
            " (.apothem/plans/; a legacy .plans/ tree is upgraded via"
            " apothem migrate-workspace) — confidence-scored"
            " per-suite at the plans-provenance pass; canonical"
            " destination is the host project the suite was authored"
            " against.",
            ["plans-discipline"],
        )
    # Memory: per-project state, not a refit target.
    if cls == "memory":
        return (
            "Keep",
            "Memory record (per-project state); the auto-memory rule"
            " owns lifecycle; not a refit target at this audit.",
            [],
        )
    # Genuine secret leak: highest priority.
    if _is_genuine_secret(hits):
        anchors.append("scan_secrets_pii")
        return (
            "Refine",
            "Genuine secret-candidate detected: rotate upstream, remove"
            " from working tree, verify git-history removal pre-push.",
            anchors,
        )
    severity = _max_severity(hits)
    is_orphan = rel in orphans
    header_status = record.get("header-status", "not-applicable")
    if severity == "HIGH":
        scanners = sorted({h.get("scanner", "?") for h in hits})
        anchors.extend(scanners)
        return (
            "Refine",
            f"HIGH-severity drift detected by {', '.join(scanners)};"
            " refit-pass remediation expected.",
            anchors,
        )
    if is_orphan and severity is None:
        anchors.append("capability-graph.orphans")
        return (
            "Remove",
            "Orphan in capability graph (zero inbound edges) and no"
            " drift hits — audit gate confirms remove vs. rebind.",
            anchors,
        )
    if header_status == "absent":
        anchors.append("inventory.header-status")
        return (
            "Refine",
            "SPDX-License-Identifier header absent on header-applicable"
            " file; the header-injection pass (scripts/inject-header.py)"
            " installs it.",
            anchors,
        )
    if severity == "MEDIUM":
        scanners = sorted({h.get("scanner", "?") for h in hits})
        anchors.extend(scanners)
        return (
            "Refine",
            f"MEDIUM-severity drift detected by {', '.join(scanners)};"
            " refit during the relevant per-class refit pass.",
            anchors,
        )
    if severity == "LOW":
        scanners = sorted({h.get("scanner", "?") for h in hits})
        anchors.extend(scanners)
        return (
            "Keep",
            f"LOW-severity drift only ({', '.join(scanners)}); watch-item"
            " noted but no refit required.",
            anchors,
        )
    return ("Keep", "No drift, no orphan, header status acceptable.", [])


def _emit_markdown(
    verdicts: list[dict[str, Any]],
    out_path: Path,
) -> None:
    """Render the per-file verdict table to Markdown."""
    counts: dict[str, int] = defaultdict(int)
    by_class: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for v in verdicts:
        counts[v["verdict"]] += 1
        by_class[v["class"]][v["verdict"]] += 1

    lines: list[str] = []
    lines.append("# Classification Matrix")
    lines.append("")
    lines.append("Per-file verdict from the nine-verdict matrix.")
    lines.append("")
    lines.append("## Verdict counts")
    lines.append("")
    lines.append("| Verdict | Count |")
    lines.append("|---------|------:|")
    for v in VERDICTS:
        lines.append(f"| {v} | {counts.get(v, 0)} |")
    lines.append("")
    lines.append("## Verdict counts by class")
    lines.append("")
    lines.append("| Class | " + " | ".join(VERDICTS) + " | Total |")
    lines.append("|-------|" + "|".join("------:" for _ in VERDICTS) + "|------:|")
    for cls in sorted(by_class.keys()):
        cells = [str(by_class[cls].get(v, 0)) for v in VERDICTS]
        total = sum(by_class[cls].values())
        lines.append(f"| {cls} | " + " | ".join(cells) + f" | {total} |")
    lines.append("")
    lines.append("## Per-file verdicts (narrative classes only)")
    lines.append("")
    lines.append(
        "Memory and plan-artifact rows are summarized in the counts"
        " above; per-file enumeration is restricted to narrative"
        " classes for readability."
    )
    lines.append("")
    lines.append("| Path | Class | Verdict | Justification | Evidence |")
    lines.append("|------|-------|---------|---------------|----------|")
    narrative = [v for v in verdicts if v["class"] not in {"memory", "plan-artifact"}]
    for v in sorted(narrative, key=lambda x: (x["verdict"], x["path"])):
        evidence = ", ".join(v["evidence-anchors"]) or "—"
        lines.append(
            f"| `{v['path']}` | {v['class']} | {v['verdict']} |"
            f" {v['justification']} | {evidence} |"
        )
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _classify_records(
    records: Iterable[dict[str, Any]],
    findings_by_file: dict[str, list[dict[str, Any]]],
    orphans: set[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in records:
        rel = record.get("path", "")
        hits = findings_by_file.get(rel, [])
        verdict, justification, anchors = _classify_record(record, hits, orphans)
        out.append(
            {
                "path": rel,
                "class": record.get("class", ""),
                "verdict": verdict,
                "justification": justification,
                "evidence-anchors": anchors,
                "drift-hit-count": len(hits),
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    """Assign one classification verdict per inventory artifact and emit the matrix documents.

    Loads the inventory, drift-scan findings, and orphan list; runs each file
    through the nine-verdict matrix; and writes
    ``classification-matrix.json`` / ``.md`` with a per-verdict summary.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=Path(".audit"),
    )
    parser.add_argument(
        "--md-output",
        type=Path,
        default=Path(".audit/classification-matrix.md"),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path(".audit/classification-matrix.json"),
    )
    args = parser.parse_args(argv)

    if not args.inventory.exists():
        print(
            f"error: inventory not found at {args.inventory}",
            file=sys.stderr,
        )
        return 1

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    records = inventory.get("files", [])
    findings = _load_scan_findings(args.audit_dir)
    orphans = _load_orphans(args.audit_dir / "orphans.md")
    verdicts = _classify_records(records, findings, orphans)

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(
            {
                "verdict-options": VERDICTS,
                "total-files": len(verdicts),
                "verdicts": verdicts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _emit_markdown(verdicts, args.md_output)

    counts: dict[str, int] = defaultdict(int)
    for v in verdicts:
        counts[v["verdict"]] += 1
    summary = ", ".join(f"{v}={counts[v]}" for v in VERDICTS if counts.get(v))
    print(f"classify_artifacts: {len(verdicts)} files classified [{summary}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
