# SPDX-License-Identifier: MIT

"""Shared helpers for the drift / classification scan family.

Why this module exists. The eight drift scans plus the classification
pass and the synthesis pass all share the same scaffolding: load the
inventory once, filter to the narrative-surface subset, walk those files
with a per-file callable, and emit a JSON document with a stable schema
(``generated`` ISO timestamp, ``inventory-source`` SHA256, ``hits`` array
of finding records). Centralizing the scaffolding here removes the
copy-paste pressure that would otherwise produce subtle drift between
scanner outputs.

What this module exports.

- ``CONTENT_ROOT`` — the ``src/apothem/`` content root the inventory is
  built against; the default ``--root`` for inventory-record-resolving
  scanners.
- ``load_inventory(path)`` — parse ``inventory.json`` and return its
  records as a list of dictionaries. Raises ``FileNotFoundError`` if the
  inventory is absent (the dispatcher reports prerequisite-missing).
- ``narrative_surface_filter(record)`` — predicate selecting the file
  classes whose contents carry prose / directives / configuration that
  drift scans should walk. Excludes ``memory`` (per-project state),
  ``plan-artifact`` (this suite's artifacts; auto-classified at the
  matrix step), and the audit-output tree.
- ``read_text_safely(path)`` — open a file as UTF-8 with replacement
  fallback, returning ``""`` for binary or unreadable files. Scanners
  that fail-soft on decode errors keep running across mixed-encoding
  corpora.
- ``emit_json(out_path, scanner, hits, inventory_sha)`` — write a scan
  output with the canonical envelope ``{generated, scanner,
  inventory-source-sha256, hit-count, hits}``.
- ``Hit`` — small dataclass standardizing a finding record's shape
  across scanners (``file``, ``line``, ``signal``, ``severity``,
  ``remediation``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, TypeAlias

# Per-scan callback signature: receives the resolved file path, the
# inventory record, and the file's text content; returns the hits the
# scanner found in that file.
WalkCallback: TypeAlias = Callable[[Path, dict[str, Any], str], list["Hit"]]

# The content root the drift / classification inventory is built against —
# the ``src/apothem/`` package directory, one level up from this ``audit/``
# package. It is the default ``--root`` for every inventory-record-resolving
# scanner: inventory record paths are content-root-relative (``rules/…``,
# ``hooks/…``), so a scanner resolves a file as ``CONTENT_ROOT / record["path"]``.
# Repo-root tools (instruction-surface presence, plans-provenance, header
# coverage) anchor on the repository root and keep their own ``--root`` default.
CONTENT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

NARRATIVE_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "agent",
        "command",
        "skill",
        "hook",
        "output-style",
        "statusline",
        "settings",
        "scaffolding",
        "docs",
        "mcp",
    }
)

SEVERITY_HIGH: Final[str] = "HIGH"
SEVERITY_MEDIUM: Final[str] = "MEDIUM"
SEVERITY_LOW: Final[str] = "LOW"


@dataclass(frozen=True)
class Hit:
    """A single drift / risk finding emitted by a scanner.

    The shape is intentionally narrow: every scanner records the same
    five fields so the synthesis pass can rank, sort, and group hits
    uniformly across heterogeneous scan dimensions.
    """

    file: str
    line: int
    signal: str
    severity: str
    remediation: str
    extra: dict[str, Any] = field(default_factory=dict)


def load_inventory(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Return ``(records, sha256)`` for the inventory document.

    The SHA-256 anchors every scan output to the exact inventory snapshot
    it was computed against; downstream synthesis can detect a stale
    scan by comparing the embedded hash with the current inventory's.
    """
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    records = payload.get("files", [])
    return records, sha


def narrative_surface_filter(record: dict[str, Any]) -> bool:
    """Return ``True`` for files whose contents carry directives or prose
    a drift scanner should walk.

    Memory and plan-artifact records are excluded because they carry
    per-project state and intra-suite scaffolding, neither of which the
    drift scans target. ``unknown`` records are excluded defensively;
    any unknown after the inventory pass refines its classification is
    itself a finding the inventory tool already surfaced.
    """
    cls = record.get("class", "")
    return cls in NARRATIVE_CLASSES


def read_text_safely(path: Path, max_bytes: int = 5_000_000) -> str:
    """Read a file as UTF-8 with replacement fallback; return ``""`` on
    failure or oversize.

    The 5 MB cap protects scanners from accidentally walking a binary
    blob mis-classified as text; no narrative source artifact is that
    large in practice.
    """
    try:
        if path.stat().st_size > max_bytes:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def walk_narrative_surfaces(
    records: Iterable[dict[str, Any]],
    root: Path,
    callback: Callable[[Path, dict[str, Any], str], list[Hit]],
) -> list[Hit]:
    """Apply ``callback(path, record, content)`` to every narrative
    surface and accumulate the returned hits."""
    hits: list[Hit] = []
    for record in records:
        if not narrative_surface_filter(record):
            continue
        rel = record.get("path", "")
        path = root / rel
        content = read_text_safely(path)
        if not content:
            continue
        hits.extend(callback(path, record, content))
    return hits


def emit_json(
    out_path: Path,
    scanner: str,
    hits: list[Hit],
    inventory_sha: str,
) -> None:
    """Write the canonical scan-output envelope to ``out_path``."""
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "scanner": scanner,
        "inventory-source-sha256": inventory_sha,
        "hit-count": len(hits),
        "hits": [asdict(h) for h in hits],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
