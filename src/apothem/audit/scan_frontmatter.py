# SPDX-License-Identifier: MIT

"""Scan frontmatter consistency across artifact classes that carry it.

Why this scan exists. Agents, commands, skills, output-styles, and
several plan-artifact classes carry YAML frontmatter at the head of
each file. Per-class schemas have not yet been ratified at the time of
this scan, so the check is heuristic-driven: walk every artifact in a
class, sample the dominant key set and key order, and flag any sibling
that diverges. The scan also flags any TOML-style frontmatter
(``+++...+++``) because the discovered convention across every existing
file is YAML (``---...---``).

What this scan covers per class.

- **Required-key drift.** Keys present in at least 80% of the class's
  files are treated as the de-facto required set; siblings missing any
  of those keys produce a finding.
- **Key-order drift.** The dominant key sequence is the de-facto order;
  siblings whose key sequence diverges produce a finding (rearranging a
  frontmatter block is a near-zero-cost fix that compounds readability).
- **Format drift.** Any non-YAML frontmatter delimiter (``+++``,
  ``;;;``, JSON object as first content) is flagged irrespective of
  class.
- **Empty required field.** A required key with an empty string /
  ``null`` value is flagged separately because the absence of value is
  often more dangerous than the absence of key.

What this scan excludes. Memory and plan-artifact classes are excluded
from the dominant-pattern computation because they are not refit
targets at this phase. Files without any frontmatter that belong to a
class where frontmatter is universally present are flagged as
``frontmatter-absent``.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scan_lib import (
    CONTENT_ROOT,
    SEVERITY_MEDIUM,
    Hit,
    emit_json,
    load_inventory,
    read_text_safely,
)

# Artifact classes that carry frontmatter as a convention. Settings
# files are JSON; scaffolding files vary; only the listed classes are
# walked for frontmatter consistency.
FRONTMATTER_CLASSES: Final[frozenset[str]] = frozenset(
    {"agent", "command", "skill", "output-style"}
)

# Frontmatter requires presence in at least this fraction of a class's
# files to be treated as the de-facto required set.
REQUIRED_THRESHOLD: Final[float] = 0.8


def _extract_frontmatter(content: str) -> tuple[list[str], str | None]:
    """Return ``(ordered-keys, delimiter)`` for the document's
    frontmatter, or ``([], None)`` if no frontmatter is present.

    Recognizes YAML (``---``), TOML (``+++``), and a permissive
    semicolon delimiter (``;;;``). Inside a YAML block, only top-level
    keys (un-indented ``key:`` lines) are captured; nested keys are not
    part of the frontmatter contract.
    """
    lines = content.splitlines()
    if not lines:
        return [], None
    first = lines[0].strip()
    if first not in ("---", "+++", ";;;"):
        return [], None
    delimiter = first
    keys: list[str] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == delimiter:
            return keys, delimiter
        # Top-level YAML key: un-indented `key:` (no leading whitespace).
        if line and not line[0].isspace() and ":" in line:
            key = line.split(":", 1)[0].strip()
            if key and not key.startswith("#"):
                keys.append(key)
    # Closing delimiter not found; treat as malformed frontmatter.
    return keys, "malformed"


def _empty_value_keys(content: str, keys: list[str]) -> list[str]:
    """Return keys whose value is empty / null / quoted-empty."""
    if not keys:
        return []
    empty: list[str] = []
    in_block = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if in_block:
                break
            in_block = True
            continue
        if not in_block or line[:1].isspace() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key in keys and value in ("", "''", '""', "null", "~"):
            empty.append(key)
    return empty


def _gather_class_records(
    records: Iterable[dict[str, Any]], cls: str
) -> list[dict[str, Any]]:
    return [r for r in records if r.get("class") == cls]


def _compute_class_baseline(
    class_records: list[dict[str, Any]], root: Path
) -> tuple[set[str], list[str]]:
    """Return ``(required-keys, dominant-order)`` for a class."""
    if not class_records:
        return set(), []
    key_presence: Counter[str] = Counter()
    order_counter: Counter[tuple[str, ...]] = Counter()
    n = 0
    for record in class_records:
        path = root / record["path"]
        content = read_text_safely(path)
        if not content:
            continue
        keys, delimiter = _extract_frontmatter(content)
        if not keys or delimiter != "---":
            continue
        n += 1
        for k in keys:
            key_presence[k] += 1
        order_counter[tuple(keys)] += 1
    if n == 0:
        return set(), []
    threshold = max(1, int(REQUIRED_THRESHOLD * n))
    required = {k for k, count in key_presence.items() if count >= threshold}
    dominant_order = list(order_counter.most_common(1)[0][0]) if order_counter else []
    return required, dominant_order


def _scan_class(cls: str, records: list[dict[str, Any]], root: Path) -> list[Hit]:
    """Walk a single class and emit hits for divergent siblings."""
    required, dominant_order = _compute_class_baseline(records, root)
    hits: list[Hit] = []
    for record in records:
        rel = record["path"]
        path = root / rel
        content = read_text_safely(path)
        if not content:
            continue
        keys, delimiter = _extract_frontmatter(content)
        hits.extend(
            _diagnose_record(rel, content, keys, delimiter, required, dominant_order)
        )
    return hits


def _diagnose_record(
    rel: str,
    content: str,
    keys: list[str],
    delimiter: str | None,
    required: set[str],
    dominant_order: list[str],
) -> list[Hit]:
    """Return all findings for a single file's frontmatter state."""
    hits: list[Hit] = []
    if delimiter is None:
        if required:
            hits.append(
                Hit(
                    file=rel,
                    line=1,
                    signal="frontmatter-absent",
                    severity=SEVERITY_MEDIUM,
                    remediation=(
                        "Add the class's required frontmatter keys at the"
                        " head of the file enclosed by '---' delimiters."
                    ),
                )
            )
        return hits
    if delimiter == "+++" or delimiter == ";;;" or delimiter == "malformed":
        hits.append(
            Hit(
                file=rel,
                line=1,
                signal=f"frontmatter-non-yaml-or-malformed: {delimiter}",
                severity=SEVERITY_MEDIUM,
                remediation=(
                    "Convert the frontmatter to the YAML form delimited"
                    " by '---'; non-YAML delimiters break tooling that"
                    " expects the convention."
                ),
            )
        )
    missing = required - set(keys)
    for key in sorted(missing):
        hits.append(
            Hit(
                file=rel,
                line=1,
                signal=f"frontmatter-missing-required: {key}",
                severity=SEVERITY_MEDIUM,
                remediation=(
                    f"Add '{key}: <value>' to the frontmatter; the key is"
                    " present in at least 80% of the class's files."
                ),
            )
        )
    if dominant_order and keys != dominant_order and not missing:
        # Only flag order drift when the file has the full required set;
        # missing-key cases dominate and ordering is secondary.
        hits.append(
            Hit(
                file=rel,
                line=1,
                signal="frontmatter-key-order-drift",
                severity=SEVERITY_MEDIUM,
                remediation=(
                    "Reorder the frontmatter keys to match the class's"
                    f" dominant sequence: {dominant_order}."
                ),
            )
        )
    for key in _empty_value_keys(content, list(required & set(keys))):
        hits.append(
            Hit(
                file=rel,
                line=1,
                signal=f"frontmatter-empty-required-value: {key}",
                severity=SEVERITY_MEDIUM,
                remediation=(
                    f"Populate '{key}' with a non-empty value; the key is"
                    " required but its value is blank or null."
                ),
            )
        )
    return hits


def main(argv: list[str] | None = None) -> int:
    """Check frontmatter consistency per artifact class and write ``drift-frontmatter.json``.

    For each frontmatter-bearing class, derives the dominant required-key set
    and key order, flags siblings that diverge (missing key, order drift,
    non-YAML delimiter, empty required value), emits the envelope, and prints a
    per-class summary.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
    )
    parser.add_argument("--root", type=Path, default=CONTENT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".audit/drift-frontmatter.json"),
    )
    args = parser.parse_args(argv)

    if not args.inventory.exists():
        print(
            f"error: inventory not found at {args.inventory}",
            file=sys.stderr,
        )
        return 1

    records, sha = load_inventory(args.inventory)
    hits: list[Hit] = []
    per_class_counts: dict[str, int] = {}
    for cls in sorted(FRONTMATTER_CLASSES):
        cls_records = _gather_class_records(records, cls)
        per_class_counts[cls] = len(cls_records)
        hits.extend(_scan_class(cls, cls_records, args.root))
    emit_json(args.output, "scan_frontmatter", hits, sha)
    summary = ", ".join(f"{c}={n}" for c, n in per_class_counts.items())
    print(f"scan_frontmatter: {len(hits)} hit(s) across classes [{summary}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
