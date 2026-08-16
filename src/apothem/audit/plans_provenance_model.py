# SPDX-License-Identifier: MIT

"""Why this module exists — the shapes every provenance stage speaks in.

Three dataclasses carry a plan file's provenance from the body scan to the
emitted documents: what a scan observed, what a suite was judged to be, and
what a single file's record says. Every stage of the pipeline reads or writes
one of them, and none of the stages needs to know how the others work.

Scope. Pure declaration, no behavior. ``ProvenanceRecord`` in particular is
the source of truth for the JSON envelope — each field surfaces in the output
document under a kebab-cased spelling of its name — so a change here is a
change to a published contract, not an internal detail.

Holding them here is also what keeps the pipeline acyclic. The builder
resolves records and the renderer emits them; both depend on these shapes, and
neither has to depend on the other's module to name them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Signals:
    """Per-file body-scan signal set."""

    repo_urls: list[str] = field(default_factory=list)
    abs_paths: list[str] = field(default_factory=list)
    file_refs: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    eco_path_hits: int = 0


@dataclass
class SuiteVerdict:
    """The suite-level destination + confidence + rationale fragments
    every file in the suite inherits.

    The verdict is computed once per suite from the suite-name
    heuristic plus the aggregated body signals; the per-file records
    surface the verdict alongside their individual signal sets.
    """

    suite: str
    file_count: int
    destination: str
    confidence: str
    rationale: list[str]
    aggregate_repo_urls: list[str]
    aggregate_abs_paths: list[str]
    eco_signal_density: float


@dataclass
class ProvenanceRecord:
    """Provenance record for a single plan file.

    The shape is the source of truth for the JSON envelope: every field
    here surfaces in the output document with an identical key.
    """

    path: str
    suite: str
    mtime: str
    sha256: str
    line_count: int
    frontmatter_project: str | None
    signals: Signals
    inferred_destination: str
    confidence: str
    proposed_destination_filename: str
    notes: list[str] = field(default_factory=list)
