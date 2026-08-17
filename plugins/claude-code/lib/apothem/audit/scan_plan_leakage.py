# SPDX-License-Identifier: MIT

"""Detect planning-vocabulary leaking into shipped narrative artifacts.

Why this scan exists. Codebase content destined for the public-facing
repository must speak its own natural domain language and must never
carry references to the planning vocabulary that produced it. Stage
labels (``Phase NN``, ``Wave N``), planning-artifact filenames
(``PHASE.md``, ``MASTER-PLAN.md``, ``PROGRESS.md``, ``PLAN-NOTES.md``),
intra-suite directory shapes (``_inputs/``, ``_outputs/``), mandate
identifiers (``CM-N``, ``TM-N``, ``M-N``), decision / waypoint
identifiers (launch-decision and waypoint IDs), open-question stubs
(``OQ-N``), unfilled confirmation placeholders
(``<USER-CONFIRM:...>``), audit-finding identifiers (``F\\d+``),
risk / constraint identifiers (``R-N``, ``C-N``), predecessor brand
names (``claudeloom``, ``ClaudeLoom``), and the predecessor-suite
folder names are all signals of unsealed planning-context bleed-through.

What this scan covers. Eight regex families, one per category:

- **Stage labels** — ``\\bPhase\\s+\\d+\\b``, ``\\bWave\\s+\\d+\\b``,
  ``\\bSprint\\s+\\d+\\b`` patterns. Bare ``phase`` / ``wave`` / ``sprint``
  in lower-case prose is NOT flagged (false-positive risk on natural
  English use of those words).
- **Planning-artifact filenames** — literal ``PHASE.md``,
  ``MASTER-PLAN``/``MASTER-PLAN.md``, ``PROGRESS.md``,
  ``PLAN-NOTES``/``PLAN-NOTES.md``, and ``PREAMBLE.md`` token references.
- **Intra-suite directory references** — ``_inputs/`` and ``_outputs/``
  tokens.
- **Re-stage verb labels** — ``re-execute``, ``re-audit``, ``re-sweep``,
  ``re-author`` as hyphenated compounds (these are planning-cycle
  labels; ``rerun`` / ``redo`` as natural verbs are not flagged).
- **Predecessor brand tokens** — ``claudeloom``, ``ClaudeLoom``;
  ``hardening`` only when paired with a planning context marker
  (``hardening suite``, ``hardening phase``, ``hardening REPORT``).
- **Plan-suite directory names** — legacy suite slugs that identify
  predecessor planning cycles.
- **Mandate / decision identifiers** — ``CM-\\d+``, ``TM-\\d+``,
  ``\\bM-\\d+\\b``, launch-decision IDs, waypoint IDs, ``OQ-\\d+``,
  ``R-\\d+``, ``C-\\d+``, and audit-finding shape ``\\bF\\d+\\b``.
- **Unfilled confirmation placeholders** — literal
  ``<USER-CONFIRM:...>`` markers.

What this scan excludes.

- The scanner's own source file (self-skip via a sentinel-filename
  predicate) — the patterns appear in this docstring and in the regex
  family constants below as definitional references, not as leakage.
- ``CHANGELOG.md`` (where stage labels may legitimately reference
  prior planning cycles for historical context).
- The shared narrative-surface filter already excludes ``memory`` and
  ``plan-artifact`` records, so the inventory-driven walk never visits
  plan-suite-internal artifacts.

Invocation surface. Two modes mirror the sibling scanner family:

1. Inventory-driven (default; sibling-convergent with
   ``scan_stale_tokens``):
   ``python -m apothem.audit.scan_plan_leakage --inventory
   .audit/inventory.json --root . --output .audit/leakage.json``.
2. Ad-hoc path-walking (fallback when no inventory is available):
   ``python -m apothem.audit.scan_plan_leakage --path <dir-or-file>
   [--format json|text] [--exclude <glob>]``.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scan_lib import (
    CONTENT_ROOT,
    NARRATIVE_CLASSES,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    Hit,
    WalkCallback,
    emit_json,
    load_inventory,
    read_text_safely,
    walk_narrative_surfaces,
)

# ---------------------------------------------------------------------
# Regex families (one per leakage category).
# ---------------------------------------------------------------------

# Stage labels: capitalised, followed by a digit. ``\bPhase\s+\d+\b`` is
# narrow enough to skip natural-English "phase of the moon" prose.
_STAGE_LABEL = re.compile(r"\b(?:Phase|Wave|Sprint)\s+\d+[A-Z]?\b")

# Planning-artifact filenames and intra-suite directory tokens. Listed
# literally because each is itself a load-bearing string the inventory
# scan never sees in legitimate shipped content.
_PLAN_FILE_TOKENS = re.compile(
    r"\b("
    r"PHASE\.md|MASTER-PLAN(?:\.md)?|PROGRESS\.md|PLAN-NOTES(?:\.md)?"
    r"|PREAMBLE\.md"
    r")\b"
)

# Intra-suite directory references. The underscore prefix and trailing
# slash distinguish these from natural prose.
_PLAN_DIR_TOKENS = re.compile(r"(?<![A-Za-z0-9])_(?:inputs|outputs)/")

# Re-stage verb labels: hyphenated compounds used as planning-cycle
# vocabulary. Bare ``rerun`` / ``redo`` are not flagged.
_RESTAGE_VERBS = re.compile(
    r"\bre-(?:execute|audit|sweep|author|generate|review|emit|run|"
    r"verify|validate)\b",
    re.IGNORECASE,
)

# Predecessor brand tokens and contextual ``hardening`` matches.
_CLAUDELOOM_TOKEN = re.compile(r"\b[Cc]laude[Ll]oom\b")
_HARDENING_CONTEXTUAL = re.compile(
    r"\bhardening\s+(?:suite|phase|REPORT|plan|cycle|cutover|wave|"
    r"sprint|PREAMBLE)\b",
    re.IGNORECASE,
)

# Plan-suite directory names. These are full-slug shapes; partial matches on
# ``apothem`` alone would be over-broad. Slug fragments are split across
# adjacent literals so the scanner can detect leakage without carrying exact
# release-planning folder names as narrative prose.
_VERSIONED_LAUNCH_SLUG = r"-".join(("apothem", r"v\d+\.\d+\.\d+", "launch"))
_LEGACY_SUITE_SLUGS = ("-".join(("apothem", "production", "hardening")),)
_SUITE_SLUGS = re.compile(
    r"\b(?:"
    + _VERSIONED_LAUNCH_SLUG
    + "|"
    + "|".join(re.escape(slug) for slug in _LEGACY_SUITE_SLUGS)
    + r")\b"
)

# Mandate / decision / waypoint / open-question / risk / constraint /
# audit-finding identifiers. Each pattern is anchored to its prefix
# letters so bare numbers in prose do not match.
_MANDATE_IDS = re.compile(
    r"\b(?:CM|TM)-\d+\b"
    r"|(?<![A-Za-z0-9])M-\d+(?![A-Za-z0-9])"
    r"|\bD-[A-Z]+-\d+\b"
    r"|\bW-[A-Z]+-\d+\b"
    r"|\bOQ-\d+\b"
    r"|\bR-\d+\b"
    r"|\bC-\d+\b"
    r"|\bF\d{2,}\b"
)

# Unfilled confirmation placeholders. These must never reach shipped
# artifacts; the matcher is the hard block at the pre-emission gate.
_USER_CONFIRM = re.compile(r"<USER-CONFIRM:[^>]*>")

# File-level exemptions: legitimate historical references.
_FILE_EXEMPT = frozenset({"CHANGELOG.md"})

# Sentinel: skip the scanner's own source so the regex-family constants
# above do not self-match.
_SELF_FILENAME = "scan_plan_leakage.py"

# Default file extensions walked in ad-hoc path mode.
_NARRATIVE_SUFFIXES = frozenset(
    {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".py",
        ".sh",
        ".ps1",
        ".yml",
        ".yaml",
        ".toml",
        ".json",
    }
)


# ---------------------------------------------------------------------
# Per-line scanners.
# ---------------------------------------------------------------------


def _scan_stage_labels(rel: str, lineno: int, line: str) -> list[Hit]:
    """Emit hits for capitalised stage labels followed by a number."""
    hits: list[Hit] = []
    for match in _STAGE_LABEL.finditer(line):
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"stage-label: {match.group(0)}",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Rewrite the prose in natural domain language; the"
                    " shipped artifact must not reference the planning"
                    " stage that produced it."
                ),
            )
        )
    return hits


def _scan_plan_artifacts(rel: str, lineno: int, line: str) -> list[Hit]:
    """Emit hits for planning-artifact filename and directory tokens."""
    hits: list[Hit] = []
    for match in _PLAN_FILE_TOKENS.finditer(line):
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"plan-artifact-filename: {match.group(0)}",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Remove the reference to the planning artifact;"
                    " shipped content must not name intra-suite files."
                ),
            )
        )
    for match in _PLAN_DIR_TOKENS.finditer(line):
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"plan-directory-token: {match.group(0)}",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Remove the intra-suite directory reference;"
                    " shipped content must not name _inputs/ or"
                    " _outputs/ directories."
                ),
            )
        )
    return hits


def _scan_restage_verbs(rel: str, lineno: int, line: str) -> list[Hit]:
    """Emit hits for hyphenated re-stage verb labels."""
    hits: list[Hit] = []
    for match in _RESTAGE_VERBS.finditer(line):
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"restage-verb: {match.group(0)}",
                severity=SEVERITY_MEDIUM,
                remediation=(
                    "Replace the planning-cycle verb with a natural"
                    " equivalent (``rerun``, ``redo``, ``repeat``) or"
                    " remove the directive entirely."
                ),
            )
        )
    return hits


def _scan_brand_tokens(rel: str, lineno: int, line: str) -> list[Hit]:
    """Emit hits for predecessor brand tokens."""
    hits: list[Hit] = []
    for match in _CLAUDELOOM_TOKEN.finditer(line):
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"predecessor-brand: {match.group(0)}",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Replace with the current brand token ``apothem``;"
                    " predecessor brand names must not appear in"
                    " shipped artifacts."
                ),
            )
        )
    for match in _HARDENING_CONTEXTUAL.finditer(line):
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"hardening-context: {match.group(0)}",
                severity=SEVERITY_MEDIUM,
                remediation=(
                    "Rewrite to remove the reference to the predecessor"
                    " hardening suite; shipped content must speak its"
                    " own domain language."
                ),
            )
        )
    for match in _SUITE_SLUGS.finditer(line):
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"plan-suite-slug: {match.group(0)}",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Remove the plan-suite slug; shipped content must"
                    " not name the planning suite that produced it."
                ),
            )
        )
    return hits


def _scan_mandate_ids(rel: str, lineno: int, line: str) -> list[Hit]:
    """Emit hits for mandate / decision / audit-finding identifiers."""
    hits: list[Hit] = []
    for match in _MANDATE_IDS.finditer(line):
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"plan-internal-id: {match.group(0)}",
                severity=SEVERITY_MEDIUM,
                remediation=(
                    "Replace the plan-internal identifier with a natural"
                    " description of what the identifier names, or"
                    " remove the reference if it carried no semantic"
                    " load."
                ),
            )
        )
    return hits


def _scan_user_confirm(rel: str, lineno: int, line: str) -> list[Hit]:
    """Emit hits for unfilled ``<USER-CONFIRM:...>`` placeholders."""
    hits: list[Hit] = []
    for match in _USER_CONFIRM.finditer(line):
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"unfilled-user-confirm: {match.group(0)}",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Resolve the unfilled inquiry placeholder before"
                    " shipping; unresolved confirmations must never"
                    " reach a shipped artifact."
                ),
            )
        )
    return hits


def _is_self(path_str: str) -> bool:
    """Return True if the path is the scanner's own source file."""
    return Path(path_str).name == _SELF_FILENAME


def _is_exempt(rel: str) -> bool:
    """Return True if the file is exempt from the leakage sweep."""
    return Path(rel).name in _FILE_EXEMPT or _is_self(rel)


def _scan_line(rel: str, lineno: int, line: str) -> list[Hit]:
    """Apply every leakage scanner to a single line."""
    hits: list[Hit] = []
    hits.extend(_scan_stage_labels(rel, lineno, line))
    hits.extend(_scan_plan_artifacts(rel, lineno, line))
    hits.extend(_scan_restage_verbs(rel, lineno, line))
    hits.extend(_scan_brand_tokens(rel, lineno, line))
    hits.extend(_scan_mandate_ids(rel, lineno, line))
    hits.extend(_scan_user_confirm(rel, lineno, line))
    return hits


def _scan_callback() -> WalkCallback:
    """Build the inventory-mode per-file scanner closure."""

    def _walk(path: Path, record: dict[str, Any], content: str) -> list[Hit]:
        rel = record["path"]
        if _is_exempt(rel):
            return []
        hits: list[Hit] = []
        for lineno, line in enumerate(content.splitlines(), start=1):
            hits.extend(_scan_line(rel, lineno, line))
        return hits

    return _walk


# ---------------------------------------------------------------------
# Ad-hoc path-walking mode (fallback when inventory absent).
# ---------------------------------------------------------------------


def _iter_paths(root: Path, exclude_globs: list[str]) -> list[Path]:
    """Yield narrative-suffix files under ``root`` honoring excludes."""
    if root.is_file():
        if _excluded(root, root.parent, exclude_globs):
            return []
        return [root]
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in _NARRATIVE_SUFFIXES:
            continue
        if _excluded(p, root, exclude_globs):
            continue
        out.append(p)
    return out


def _excluded(path: Path, root: Path, globs: list[str]) -> bool:
    """Return True if ``path`` matches any of the exclude globs."""
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = path.as_posix()
    return any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(path.name, g) for g in globs)


def _scan_path_mode(root: Path, exclude_globs: list[str]) -> list[Hit]:
    """Walk ``root`` and accumulate hits across every narrative file."""
    hits: list[Hit] = []
    for path in _iter_paths(root, exclude_globs):
        try:
            rel = path.relative_to(root if root.is_dir() else root.parent)
        except ValueError:
            rel = path
        rel_str = rel.as_posix()
        if _is_exempt(rel_str):
            continue
        content = read_text_safely(path)
        if not content:
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            hits.extend(_scan_line(rel_str, lineno, line))
    return hits


# ---------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------


def _emit_text(hits: list[Hit], stream: TextIO) -> None:
    """Write hits in one-line-per-hit form to ``stream``."""
    for h in hits:
        stream.write(f"{h.file}:{h.line}: [{h.severity}] {h.signal}\n")


def main(argv: list[str] | None = None) -> int:
    """Dispatch to inventory-driven or ad-hoc path-walking plan-leakage scanning.

    Routes to the ad-hoc path-walking scan when ``--path`` is given, otherwise
    to the sibling-convergent inventory-driven scan; each mode delegates to its
    ``_run_*_mode`` helper.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
        help="Inventory JSON (sibling-convergent mode).",
    )
    parser.add_argument("--root", type=Path, default=CONTENT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".audit/leakage.json"),
        help="Output path for the JSON envelope (inventory mode).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help=(
            "Ad-hoc mode: scan this directory or file directly,"
            " bypassing the inventory."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Ad-hoc mode output format (default: text).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob to exclude (ad-hoc mode; may be repeated).",
    )
    args = parser.parse_args(argv)

    if args.path is not None:
        return _run_path_mode(args)
    return _run_inventory_mode(args)


def _run_inventory_mode(args: argparse.Namespace) -> int:
    """Execute the sibling-convergent inventory-driven scan."""
    if not args.inventory.exists():
        print(
            f"error: inventory not found at {args.inventory}; pass"
            " --path for ad-hoc mode",
            file=sys.stderr,
        )
        return 1
    records, sha = load_inventory(args.inventory)
    hits = walk_narrative_surfaces(records, args.root, _scan_callback())
    emit_json(args.output, "scan_plan_leakage", hits, sha)
    narrative_count = sum(1 for r in records if r.get("class") in NARRATIVE_CLASSES)
    by_signal: dict[str, int] = {}
    for h in hits:
        kind = h.signal.split(":", 1)[0]
        by_signal[kind] = by_signal.get(kind, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_signal.items()))
    print(
        f"scan_plan_leakage: {len(hits)} hit(s) across "
        f"{narrative_count} narrative files [{summary or 'none'}]"
    )
    return 0


def _run_path_mode(args: argparse.Namespace) -> int:
    """Execute the ad-hoc path-walking scan."""
    root = args.path
    if not root.exists():
        print(f"error: path not found: {root}", file=sys.stderr)
        return 1
    hits = _scan_path_mode(root, list(args.exclude))
    if args.format == "json":
        payload = {
            "scanner": "scan_plan_leakage",
            "hit-count": len(hits),
            "hits": [asdict(h) for h in hits],
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        _emit_text(hits, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
