# SPDX-License-Identifier: MIT

"""Advisory: flag plan-suite infra files whose Recommended-Next-Step footer
drifts from the suite's recorded next pipeline stage.

Why this validator exists. Plan-suite infrastructure files (``PROGRESS.md``,
``MASTER-PLAN.md``, ``MASTER-INDEX.md``, ``TRACE-MATRIX.md``) can close with a
``## Recommended Next Step`` footer naming the pipeline stage the operator
should run next (e.g. "Run ``/plan-design``"). The ``recommend-next-step``
matcher only scopes ``commands/``, ``skills/``, and ``phases/`` artifacts, and
the per-write gate short-circuits ``.plans/`` paths, so nothing mechanically
verifies that an infra footer still matches the suite's *recorded* next stage.
Stale footers consequently survive review cycles, directly contradicting the
suite's own ``PROGRESS.md``.

Scope and ground truth. This validator compares a footer's ``/plan-*`` pipeline
stage against the suite's recorded next ``/plan-*`` stage. It reads that
recorded stage from ``PROGRESS.md`` in two places, supporting both the
canonical plan-suite template and the meta-pipeline-tracking variant:

- **Tracker** — a table under ``## Pipeline Tracker`` *or* ``## Phase Tracker``;
  the row whose status cell is marked ``NEXT`` supplies its first ``/plan-*``
  token.
- **Next action** — the Resumption Contract field labelled "Next action",
  written either as a ``- **Next action (imperative):** Run `/plan-X``` bullet
  or as a ``**Next action:** ...`` field. The extraction is bounded to that one
  field so a ``/plan-*`` token in a later field or in ``### Active Decisions``
  never leaks in.

The Resumption Contract is authoritative; the tracker NEXT row is the
cross-check. When both name a ``/plan-*`` stage and disagree, ``PROGRESS.md`` is
internally inconsistent — itself a finding. The canonical next stage is the
Next-action stage when present, else the tracker NEXT stage.

When there is no machine-readable next *pipeline stage* — e.g. a phase-execution
suite whose Next action is "Execute Phase 05" and whose tracker lists phase IDs
rather than ``/plan-*`` stages — the validator cannot compare a footer against a
``/plan-*`` ground truth without guessing. Rather than silently passing such a
suite, it records an advisory ``note`` naming every footer it left unvalidated.

Advisory by default. ``_main`` prints the report and exits 0 regardless of
findings; ``--strict`` exits 2 on findings. The ``check()`` verdict
(``passed = not findings``) is honest either way; only the exit code is
advisory. Notes never flip ``passed``.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "plan-next-step-consistency-grep"
RULE_ANCHOR: Final[str] = "rules/recommend-next-step.md"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Opt-in flag that turns the advisory CLI into a gating one.
STRICT_FLAG: Final[str] = "--strict"

# The plan-suite root directory, relative to the inspected project root. The
# sole canonical project-local plans location is the shared ``.apothem/plans``;
# a legacy ``.plans`` tree is no longer canonical — operators upgrade it via
# ``apothem migrate-workspace``.
APOTHEM_PLANS_RELPATH: Final[tuple[str, str]] = (".apothem", "plans")

# The recorded-state source. A suite without it carries no machine-readable
# next-stage record and is skipped (no false positives on stateless suites).
PROGRESS_FILENAME: Final[str] = "PROGRESS.md"

# Infra files that carry a `## Recommended Next Step` footer pointing at a
# pipeline stage. PROGRESS.md is both the recorded-state source and an infra
# surface carrying its own footer (the in-file self-contradiction case).
INFRA_FILENAMES: Final[tuple[str, ...]] = (
    "PROGRESS.md",
    "MASTER-PLAN.md",
    "MASTER-INDEX.md",
    "TRACE-MATRIX.md",
)

# A pipeline-stage token in either written form: the canonical first-class
# command form `/plan-<stage>` or the legacy space-separated dispatch form
# `/plan <stage>`. The stage word is captured from the closed seven-stage set
# so backticks and trailing punctuation are never captured. Matches are
# normalized to the canonical `/plan-<stage>` form before comparison.
_STAGE_RE: Final[re.Pattern[str]] = re.compile(
    r"/plan[ -](spec|generate|design|review|audit|execute|status)\b"
)

# Tracker section headings. The canonical template uses `## Phase Tracker`; the
# meta-pipeline-tracking variant uses `## Pipeline Tracker`. Both are accepted.
_PIPELINE_TRACKER_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+Pipeline\s+Tracker\s*$"
)
_PHASE_TRACKER_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Phase\s+Tracker\s*$")
_RESUMPTION_CONTRACT_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+Resumption\s+Contract\s*$"
)

# Footer headings. The singular `## Recommended Next Step` is the canonical
# recommend-next-step block; the multi-action `## Next Steps` form is treated as
# a footer only when it carries a `**Recommended**` marker (otherwise it is a
# plain phase-todo list, as the canonical template emits, not a footer).
_RECOMMENDED_FOOTER_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+Recommended\s+Next\s+Step\s*$"
)
_NEXT_STEPS_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Next\s+Steps\s*$")
_ANY_H2_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+\S")

# The Resumption Contract field naming the next imperative action.
_NEXT_ACTION_RE: Final[re.Pattern[str]] = re.compile(r"next\s+action", re.IGNORECASE)
# A line that begins a new structural element (heading, list bullet, or bold
# field label) — the boundary that ends the Next-action field's continuation.
_FIELD_START_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(?:#{1,6}\s|[-*]\s|\*\*)")
# A tracker status cell marked NEXT — bolded `**NEXT**` or a cell whose sole
# alphabetic content is NEXT (e.g. `⏭️ NEXT`). Tight, so prose "next" in an
# artifact/detail cell does not register a non-NEXT row as the next stage.
_BOLD_NEXT_RE: Final[re.Pattern[str]] = re.compile(r"\*\*\s*NEXT\s*\*\*", re.IGNORECASE)
# Recommended marker inside a multi-action `## Next Steps` block.
_RECOMMENDED_RE: Final[re.Pattern[str]] = re.compile(r"\*\*Recommended\*\*")


@dataclass(frozen=True)
class Finding:
    """One infra-file footer (or PROGRESS.md marker) inconsistent with state."""

    surface: str
    suite: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result across every plan suite under the root."""

    grep: str
    root: str
    suites_inspected: int
    files_inspected: int
    passed: bool
    advisory: bool
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "grep": self.grep,
            "root": self.root,
            "suites_inspected": self.suites_inspected,
            "files_inspected": self.files_inspected,
            "passed": self.passed,
            "advisory": self.advisory,
            "findings": [asdict(f) for f in self.findings],
            "notes": list(self.notes),
        }
        return json.dumps(payload, indent=2)


def _read_lines(path: Path) -> list[str] | None:
    """Return the file's lines, or None when it is absent or unreadable."""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def _rel(path: Path, root: Path) -> str:
    """Return path relative to root as a POSIX string, else the full path."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _first_section_body(
    lines: list[str], *heading_res: re.Pattern[str]
) -> list[str] | None:
    """Return the lines under the first matching H2 heading, up to the next H2.

    The first heading in ``heading_res`` to appear in ``lines`` wins. Returns
    None when none of the headings is present (distinct from an empty body).
    """
    start: int | None = None
    for i, line in enumerate(lines):
        if any(heading_re.match(line) for heading_re in heading_res):
            start = i
            break
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start + 1 :]:
        if _ANY_H2_RE.match(line):
            break
        body.append(line)
    return body


def _first_stage(lines: list[str]) -> str | None:
    """Return the first pipeline-stage token across the lines, normalized.

    Both written forms are recognized; the returned token is always the
    canonical ``/plan-<stage>`` form so comparisons are form-agnostic.
    """
    for line in lines:
        match = _STAGE_RE.search(line)
        if match:
            return f"/plan-{match.group(1)}"
    return None


def _stage_preferring_recommended(body: list[str]) -> str | None:
    """Return the footer stage, preferring the ``**Recommended**`` line."""
    recommended = [line for line in body if _RECOMMENDED_RE.search(line)]
    if recommended:
        stage = _first_stage(recommended)
        if stage is not None:
            return stage
    return _first_stage(body)


def _resumption_next_stage(lines: list[str]) -> str | None:
    """Return the stage named by the Resumption Contract 'Next action' field.

    The extraction is bounded to the Next-action field: its label line plus any
    wrapped continuation, stopping at the first blank line, heading, list
    bullet, or bold field label. A ``/plan-*`` token in a later field or in
    ``### Active Decisions`` is therefore never picked up. Returns None when the
    field is absent or is an execution imperative with no ``/plan-*`` token.
    """
    body = _first_section_body(lines, _RESUMPTION_CONTRACT_RE)
    if body is None:
        return None
    idx = next(
        (i for i, line in enumerate(body) if _NEXT_ACTION_RE.search(line)),
        None,
    )
    if idx is None:
        return None
    block = [body[idx]]
    for line in body[idx + 1 :]:
        if not line.strip() or _FIELD_START_RE.match(line):
            break
        block.append(line)
    return _first_stage(block)


def _cell_marks_next(cell: str) -> bool:
    """Return True iff a tracker status cell marks the row as the next stage."""
    if _BOLD_NEXT_RE.search(cell):
        return True
    alpha = re.sub(r"[^A-Za-z]", "", cell).upper()
    return alpha == "NEXT"


def _tracker_next_stage(lines: list[str]) -> str | None:
    """Return the stage in the tracker row marked ``NEXT``.

    Accepts both the ``## Pipeline Tracker`` and ``## Phase Tracker`` headings
    and is column-layout-agnostic: a row qualifies when any cell is a NEXT
    status marker, and the stage is the first ``/plan-*`` token in the row. A
    phase-execution tracker (phase IDs, no ``/plan-*`` tokens) yields None.
    """
    body = _first_section_body(lines, _PIPELINE_TRACKER_RE, _PHASE_TRACKER_RE)
    if body is None:
        return None
    for line in body:
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not any(_cell_marks_next(cell) for cell in cells):
            continue
        stage = _first_stage([line])
        if stage is not None:
            return stage
    return None


def _footer_stage(lines: list[str]) -> str | None:
    """Return the pipeline stage named in the Recommended-Next-Step footer.

    Prefers the singular ``## Recommended Next Step`` block. A ``## Next Steps``
    block counts as a footer only when it carries a ``**Recommended**`` marker
    (the multi-action form); a plain ``## Next Steps`` phase-todo list — as the
    canonical template emits — is not a footer and yields None. None when no
    footer names a pipeline stage.
    """
    body = _first_section_body(lines, _RECOMMENDED_FOOTER_RE)
    if body is not None:
        return _stage_preferring_recommended(body)
    body = _first_section_body(lines, _NEXT_STEPS_RE)
    if body is None:
        return None
    if not any(_RECOMMENDED_RE.search(line) for line in body):
        return None
    return _stage_preferring_recommended(body)


def _inspect_suite(
    suite_dir: Path, root: Path
) -> tuple[list[Finding], int, list[str]] | None:
    """Inspect one suite; return (findings, files-inspected, notes) or None.

    Returns None when the suite carries no ``PROGRESS.md`` (no recorded state to
    validate against). Otherwise derives the canonical next stage and compares
    every present infra file's footer against it; an underived canonical with a
    pipeline-stage footer present yields an advisory note rather than a silent
    pass.
    """
    progress = suite_dir / PROGRESS_FILENAME
    if not progress.is_file():
        return None
    progress_lines = _read_lines(progress)
    if progress_lines is None:
        return (
            [
                Finding(
                    surface=_rel(progress, root),
                    suite=suite_dir.name,
                    detail="PROGRESS.md exists but could not be read as UTF-8 text",
                )
            ],
            0,
            [],
        )

    findings: list[Finding] = []
    next_action = _resumption_next_stage(progress_lines)
    tracker_next = _tracker_next_stage(progress_lines)
    canonical = next_action or tracker_next

    # The two recorded-state markers must agree when both are present.
    if next_action and tracker_next and next_action != tracker_next:
        findings.append(
            Finding(
                surface=_rel(progress, root),
                suite=suite_dir.name,
                detail=(
                    f"PROGRESS.md internal drift — tracker marks "
                    f"`{tracker_next}` NEXT but Resumption Contract 'Next "
                    f"action' names `{next_action}`"
                ),
            )
        )

    source = (
        "Resumption Contract 'Next action'"
        if next_action
        else "Pipeline/Phase Tracker NEXT"
    )
    files_inspected = 0
    unvalidated_footers: list[str] = []
    for fname in INFRA_FILENAMES:
        infra_lines = _read_lines(suite_dir / fname)
        if infra_lines is None:
            continue
        files_inspected += 1
        footer = _footer_stage(infra_lines)
        if footer is None:
            continue
        if canonical is None:
            # No `/plan-*` ground truth to compare against; surface rather than
            # silently pass.
            unvalidated_footers.append(fname)
            continue
        if footer == canonical:
            continue
        findings.append(
            Finding(
                surface=_rel(suite_dir / fname, root),
                suite=suite_dir.name,
                detail=(
                    f"`## Recommended Next Step` names `{footer}` but the "
                    f"suite's recorded next stage is `{canonical}` ({source})"
                ),
            )
        )

    notes: list[str] = []
    if canonical is None and unvalidated_footers:
        notes.append(
            f"suite '{suite_dir.name}': recorded next pipeline stage is "
            f"indeterminate (no Pipeline/Phase Tracker NEXT row and no "
            f"`/plan-*` 'Next action'); {len(unvalidated_footers)} footer(s) "
            f"naming a pipeline stage were not validated "
            f"({', '.join(unvalidated_footers)})"
        )
    return findings, files_inspected, notes


def check(root: Path) -> GrepResult:
    """Walk every plan suite under the canonical project-local plans tree.

    The sole canonical project-local plans location is
    ``<root>/.apothem/plans``; a legacy ``<root>/.plans`` tree is no longer
    canonical — operators upgrade it via ``apothem migrate-workspace``. Suites
    under the canonical tree are inspected for footer drift.
    """
    plans_dirs = (root.joinpath(*APOTHEM_PLANS_RELPATH),)
    findings: list[Finding] = []
    notes: list[str] = []
    suites_inspected = 0
    files_inspected = 0
    for plans_dir in plans_dirs:
        if not plans_dir.is_dir():
            continue
        for suite_dir in sorted(p for p in plans_dir.iterdir() if p.is_dir()):
            outcome = _inspect_suite(suite_dir, root)
            if outcome is None:
                continue
            suite_findings, inspected, suite_notes = outcome
            suites_inspected += 1
            files_inspected += inspected
            findings.extend(suite_findings)
            notes.extend(suite_notes)
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        suites_inspected=suites_inspected,
        files_inspected=files_inspected,
        passed=not findings,
        advisory=True,
        findings=findings,
        notes=notes,
    )


def _read_input(argv: list[str]) -> tuple[Path, bool]:
    """Return (root, strict) parsed from argv; root defaults to cwd."""
    strict = STRICT_FLAG in argv
    positional = [arg for arg in argv[1:] if arg != STRICT_FLAG]
    root = Path(positional[0]) if positional else Path.cwd()
    return root, strict


def _main(argv: list[str]) -> int:
    root, strict = _read_input(argv)
    result = check(root)
    print(result.to_json())
    if strict and not result.passed:
        return EXIT_FAIL
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
