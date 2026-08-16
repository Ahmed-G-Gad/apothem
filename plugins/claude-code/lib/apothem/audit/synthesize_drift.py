# SPDX-License-Identifier: MIT

"""Synthesise the eight drift-scan outputs into a single findings doc.

Why this tool exists. The eight drift scans each emit a per-scan
JSON document; the audit-gate consolidation needs one human-readable
view ranking every finding by severity, grouping by file, and
pointing at the right refit pass. This tool produces
``drift-findings.md`` — the canonical synthesis surface.

Severity ranking:

- HIGH: secret leaks, conflicting directives, broken internal links,
  plans-discipline violations, missing CLAUDE.md mandatory blocks.
- MEDIUM: stale tokens, frontmatter violations, AI-surfaces drift,
  most non-banner emails, model identifiers.
- LOW: optional-surface presence informational hits, smart-quote /
  whitespace issues (none currently scanned).

What this tool does NOT do. It does not assign verdicts (the
classification-matrix is the verdict surface) and it does not
re-run the scans (each scanner runs independently first).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

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

_SEVERITY_ORDER: Final[list[str]] = ["HIGH", "MEDIUM", "LOW"]


@dataclass(frozen=True)
class Finding:
    """One drift finding lifted from a single scanner's JSON output.

    Flattens a scan hit into the fields the synthesis ranks and groups by:
    originating ``scanner``, ``file`` / ``line``, the ``signal`` text, its
    ``severity``, and the remediation hint.
    """

    scanner: str
    file: str
    line: int
    signal: str
    severity: str
    remediation: str


def _load_scan(scanner: str, path: Path) -> tuple[list[Finding], dict[str, Any]]:
    """Return ``(findings, envelope)`` for one scan's output."""
    if not path.exists():
        return [], {"missing": True}
    payload = json.loads(path.read_text(encoding="utf-8"))
    findings = [
        Finding(
            scanner=scanner,
            file=h.get("file", ""),
            line=int(h.get("line", 0) or 0),
            signal=h.get("signal", ""),
            severity=h.get("severity", "LOW"),
            remediation=h.get("remediation", ""),
        )
        for h in payload.get("hits", [])
    ]
    envelope = {
        "scanner": scanner,
        "hit-count": payload.get("hit-count", len(findings)),
        "missing": False,
    }
    return findings, envelope


def _gather(audit_root: Path) -> tuple[list[Finding], list[dict[str, Any]]]:
    all_findings: list[Finding] = []
    envelopes: list[dict[str, Any]] = []
    for scanner, rel_path in _SCAN_FILES:
        findings, envelope = _load_scan(scanner, audit_root / Path(rel_path).name)
        all_findings.extend(findings)
        envelopes.append(envelope)
    return all_findings, envelopes


def _group_by_severity(
    findings: Iterable[Finding],
) -> dict[str, list[Finding]]:
    by_sev: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_sev[f.severity].append(f)
    return by_sev


def _group_by_scanner(
    findings: Iterable[Finding],
) -> dict[str, list[Finding]]:
    by_scanner: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_scanner[f.scanner].append(f)
    return by_scanner


def _emit_markdown(
    findings: list[Finding],
    envelopes: list[dict[str, Any]],
    out_path: Path,
) -> None:
    by_sev = _group_by_severity(findings)
    by_scanner = _group_by_scanner(findings)
    lines: list[str] = []
    lines.append("# Drift Findings")
    lines.append("")
    lines.append(
        "Synthesised from the eight drift scans. Severity ranking per"
        " the synthesis-pass criteria; grouping is by severity first,"
        " then by scanner, then by file."
    )
    lines.append("")
    lines.append("## Per-scan summary")
    lines.append("")
    lines.append("| Scanner | Hit count | Status |")
    lines.append("|---------|----------:|--------|")
    for env in envelopes:
        if env.get("missing"):
            lines.append(f"| `{env['scanner']}` | — | output absent |")
        else:
            lines.append(f"| `{env['scanner']}` | {env['hit-count']} | scan ran |")
    lines.append("")
    lines.append("## Severity totals")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|------:|")
    for sev in _SEVERITY_ORDER:
        lines.append(f"| {sev} | {len(by_sev.get(sev, []))} |")
    lines.append("")
    for sev in _SEVERITY_ORDER:
        sev_findings = by_sev.get(sev, [])
        if not sev_findings:
            continue
        lines.append(f"## {sev} severity ({len(sev_findings)} findings)")
        lines.append("")
        per_scanner = _group_by_scanner(sev_findings)
        for scanner in sorted(per_scanner.keys()):
            scanner_findings = per_scanner[scanner]
            lines.append(f"### `{scanner}` — {len(scanner_findings)} {sev} hit(s)")
            lines.append("")
            lines.append("| File | Line | Signal | Remediation |")
            lines.append("|------|-----:|--------|-------------|")
            for f in sorted(scanner_findings, key=lambda x: (x.file, x.line)):
                signal = f.signal.replace("|", r"\|")
                remediation = f.remediation.replace("|", r"\|")
                # Truncate long signal text for table readability.
                if len(signal) > 100:
                    signal = signal[:97] + "..."
                if len(remediation) > 140:
                    remediation = remediation[:137] + "..."
                lines.append(f"| `{f.file}` | {f.line} | {signal} | {remediation} |")
            lines.append("")
    lines.append("## Per-scanner total")
    lines.append("")
    lines.append("| Scanner | Total hits |")
    lines.append("|---------|-----------:|")
    for scanner in sorted(by_scanner.keys()):
        lines.append(f"| `{scanner}` | {len(by_scanner[scanner])} |")
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Gather the eight drift-scan outputs, rank and group their findings, and write ``drift-findings.md``.

    Loads each scan's hits from the audit directory, ranks them by severity
    (HIGH / MEDIUM / LOW) then by scanner and file, emits the consolidated
    Markdown synthesis, and prints a per-severity summary line.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=Path(".audit"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".audit/drift-findings.md"),
    )
    args = parser.parse_args(argv)

    findings, envelopes = _gather(args.audit_dir)
    _emit_markdown(findings, envelopes, args.output)

    by_sev = _group_by_severity(findings)
    summary = ", ".join(f"{sev}={len(by_sev.get(sev, []))}" for sev in _SEVERITY_ORDER)
    print(
        f"synthesize_drift: {len(findings)} total findings "
        f"[{summary}] across {len(envelopes)} scans -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
