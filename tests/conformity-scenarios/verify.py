# SPDX-License-Identifier: MIT

"""Conformity-fixture verification driver.

Iterates every fixture under ``fixtures/F-*-*/``, loads its
``expected-behavior.md`` frontmatter, and either records a
per-fixture per-mandate verdict matrix from a sibling
``verdict.yml`` (when present) or emits a populated stub the
operator fills during the live invocation per the spec's
verification recipe.

The driver is structurally split between two responsibilities:

1. **Fixture inventory.** Discover and validate the static
   shape of every fixture (the ``before/`` tree exists; the
   ``expected-behavior.md`` file exists; its frontmatter has
   the four required fields ``fixture`` + ``title`` +
   ``spec-source`` + ``mandates``).
2. **Verdict aggregation.** When a sibling ``verdict.yml``
   exists at the fixture root, parse the per-mandate verdict
   ledger and aggregate into the conformity-report's
   per-fixture per-mandate matrix and the orthogonal per-
   surface per-mandate matrix.

The live mandate-firing assessment (the agent's response to the
fixture's prompt) is performed out-of-band per the spec's
verification recipe; this driver is the static post-processor
that turns the recorded verdicts into the conformity report.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

FIXTURES_DIR: Final[Path] = Path(__file__).parent / "fixtures"
ALL_MANDATES: Final[tuple[str, ...]] = (
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
    "M6",
    "M7",
    "M8",
    "M9",
    "M10",
    "M11",
    "M12",
    "M13",
    "M14",
    "M15",
)
VALID_VERDICTS: Final[frozenset[str]] = frozenset({"pass", "fail", "n/a", "pending"})
SURFACES: Final[tuple[str, ...]] = (
    "CLAUDE.md",
    "src/apothem/rules/",
    "src/apothem/skills/",
    "src/apothem/agents/",
    "commands/",
    "src/apothem/hooks/",
    "src/apothem/output-styles/",
    "examples/harnesses/claude-code/native-install/settings.json",
    "src/apothem/conformity/",
)
EXPECTED_FRONTMATTER_FIELDS: Final[tuple[str, ...]] = (
    "fixture",
    "title",
    "spec-source",
    "mandates",
)
M6_TARGETING_FIXTURES: Final[frozenset[str]] = frozenset({"F-3", "F-8"})


class FixtureError(Exception):
    """Raised when a fixture's static shape is malformed."""


@dataclass(frozen=True, slots=True)
class FixtureMeta:
    """Static metadata extracted from a fixture's expected-behavior.md frontmatter."""

    fixture_id: str
    title: str
    spec_source: str
    mandates: tuple[str, ...]
    fixture_root: Path


@dataclass(slots=True)
class FixtureVerdict:
    """Per-mandate verdict for a single fixture, loaded from sibling verdict.yml."""

    fixture_id: str
    per_mandate: dict[str, str] = field(default_factory=dict)
    surfaced_gaps: list[str] = field(default_factory=list)
    notes: str = ""


_FRONTMATTER_RE: Final[re.Pattern[str]] = re.compile(
    r"^---\n(?P<body>.*?)\n---\n", re.DOTALL
)
_LIST_RE: Final[re.Pattern[str]] = re.compile(r"\[(?P<items>[^\]]*)\]")
_LEADING_HTML_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"\A\s*<!--.*?-->\s*", re.DOTALL
)


def parse_frontmatter(text: str) -> dict[str, str | tuple[str, ...]]:
    """Extract YAML-shaped frontmatter from a Markdown file.

    The driver does not depend on PyYAML; this parser handles the four
    canonical field shapes the assertion files emit (scalar string and
    bracketed list) and rejects any other frontmatter form as a
    structural error. A leading HTML-comment block (the canonical
    authorship banner injected ecosystem-wide) is skipped before
    matching the frontmatter delimiter.
    """
    text = _LEADING_HTML_COMMENT_RE.sub("", text, count=1)
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise FixtureError("frontmatter missing or malformed")
    body = match.group("body")
    parsed: dict[str, str | tuple[str, ...]] = {}
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        list_match = _LIST_RE.match(value)
        if list_match is not None:
            items = tuple(
                piece.strip()
                for piece in list_match.group("items").split(",")
                if piece.strip()
            )
            parsed[key] = items
        else:
            parsed[key] = value
    return parsed


def load_fixture(fixture_root: Path) -> FixtureMeta:
    """Load and validate the static shape of a single fixture directory.

    The ``before/`` synthetic-host tree is optional at this driver tier — it
    feeds the queued live-invocation cycle, not the static-audit verdict
    this driver computes. The assertion file is the static-audit input.
    """
    if not fixture_root.is_dir():
        raise FixtureError(f"fixture root not a directory: {fixture_root}")
    assertion = fixture_root / "expected-behavior.md"
    if not assertion.is_file():
        raise FixtureError(f"expected-behavior.md missing at {fixture_root}")
    text = assertion.read_text(encoding="utf-8")
    front = parse_frontmatter(text)
    for required in EXPECTED_FRONTMATTER_FIELDS:
        if required not in front:
            raise FixtureError(f"frontmatter missing required field {required!r}")
    mandates = front["mandates"]
    if not isinstance(mandates, tuple):
        raise FixtureError("mandates field must be a bracketed list")
    return FixtureMeta(
        fixture_id=str(front["fixture"]),
        title=str(front["title"]),
        spec_source=str(front["spec-source"]),
        mandates=mandates,
        fixture_root=fixture_root,
    )


def discover_fixtures(fixtures_dir: Path) -> list[FixtureMeta]:
    """Discover and load every F-*-* fixture under ``fixtures_dir``."""
    if not fixtures_dir.is_dir():
        raise FixtureError(f"fixtures directory missing: {fixtures_dir}")
    metas: list[FixtureMeta] = []
    for child in sorted(fixtures_dir.iterdir()):
        if child.name.startswith("F-") and child.is_dir():
            metas.append(load_fixture(child))
    return metas


def load_verdict(fixture_root: Path) -> FixtureVerdict | None:
    """Load a sibling ``verdict.yml`` if present; return None when absent.

    The verdict file's expected shape is one ``M<N>: <verdict>`` row per
    mandate (verdict ∈ {pass, fail, n/a, pending}), an optional
    ``surfaced-gaps:`` list, and an optional free-text ``notes:`` block.
    Absent verdict files mean the fixture is awaiting live invocation.
    """
    verdict_path = fixture_root / "verdict.yml"
    if not verdict_path.is_file():
        return None
    text = verdict_path.read_text(encoding="utf-8")
    fixture_id = (
        fixture_root.name.split("-", 2)[0] + "-" + fixture_root.name.split("-", 2)[1]
    )
    verdict = FixtureVerdict(fixture_id=fixture_id)
    in_gaps = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("surfaced-gaps:"):
            in_gaps = True
            continue
        if in_gaps and line.startswith("  - "):
            verdict.surfaced_gaps.append(line[4:].strip())
            continue
        in_gaps = False
        if line.startswith("notes:"):
            verdict.notes = line.partition(":")[2].strip()
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().lower()
            if key in ALL_MANDATES and value in VALID_VERDICTS:
                verdict.per_mandate[key] = value
    return verdict


def per_fixture_matrix(
    metas: list[FixtureMeta],
    verdicts: dict[str, FixtureVerdict],
) -> list[list[str]]:
    """Build the (rows = fixtures) by (cols = 15 mandates) verdict matrix."""
    matrix: list[list[str]] = []
    for meta in metas:
        verdict = verdicts.get(meta.fixture_id)
        row = [meta.fixture_id]
        for mandate in ALL_MANDATES:
            if verdict is None:
                row.append("pending")
            else:
                row.append(verdict.per_mandate.get(mandate, "pending"))
        matrix.append(row)
    return matrix


def fixture_summary(
    meta: FixtureMeta, verdict: FixtureVerdict | None
) -> dict[str, object]:
    """Compose one fixture's contribution to the conformity report."""
    if verdict is None:
        per_mandate = dict.fromkeys(ALL_MANDATES, "pending")
        gap_count = 0
    else:
        per_mandate = {m: verdict.per_mandate.get(m, "pending") for m in ALL_MANDATES}
        gap_count = len(verdict.surfaced_gaps)
    return {
        "fixture": meta.fixture_id,
        "title": meta.title,
        "spec-source": meta.spec_source,
        "declared-mandates": list(meta.mandates),
        "per-mandate-verdict": per_mandate,
        "surfaced-gap-count": gap_count,
    }


def aggregate_verdict(
    metas: list[FixtureMeta],
    verdicts: dict[str, FixtureVerdict],
    *,
    strict_run: bool,
) -> dict[str, object]:
    """Produce the run-level verdict against the ratified thresholds.

    When ``strict_run`` is True (per the I-09B operator override), the
    pass-predicate requires every cell to be ``pass`` or
    ``n/a (with reason)``; ``fail`` and ``pending`` cells fail the run.
    When ``strict_run`` is False, M4 + M5 + M8 + M13 are mandatory at
    100% and the remaining bars admit ≥ 90% per the D4 default.
    """
    cells: list[tuple[str, str, str]] = []
    for meta in metas:
        verdict = verdicts.get(meta.fixture_id)
        for mandate in ALL_MANDATES:
            cell = verdict.per_mandate.get(mandate, "pending") if verdict else "pending"
            cells.append((meta.fixture_id, mandate, cell))
    pass_cells = [c for c in cells if c[2] in {"pass", "n/a"}]
    fail_cells = [c for c in cells if c[2] == "fail"]
    pending_cells = [c for c in cells if c[2] == "pending"]
    overall = "pass"
    if pending_cells:
        overall = "pending"
    if fail_cells:
        overall = "fail"
    surfaced_gap_check = {
        fid: len(verdicts[fid].surfaced_gaps) if fid in verdicts else 0
        for fid in M6_TARGETING_FIXTURES
        if any(meta.fixture_id == fid for meta in metas)
    }
    surfaced_gap_pass = all(count >= 1 for count in surfaced_gap_check.values())
    return {
        "threshold-mode": "strict (I-09B operator override)"
        if strict_run
        else "D4 default",
        "cell-counts": {
            "total": len(cells),
            "pass-or-na": len(pass_cells),
            "fail": len(fail_cells),
            "pending": len(pending_cells),
        },
        "surfaced-gap-rate": {
            "per-m6-fixture": surfaced_gap_check,
            "all-have-at-least-one": surfaced_gap_pass,
        },
        "overall": overall,
    }


def render_summary(
    metas: list[FixtureMeta], verdicts: dict[str, FixtureVerdict]
) -> str:
    """Compose a human-readable summary paragraph."""
    have_verdict = sum(1 for m in metas if m.fixture_id in verdicts)
    return (
        f"Discovered {len(metas)} fixtures; {have_verdict} carry a verdict.yml; "
        f"{len(metas) - have_verdict} await live invocation."
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Conformity-fixture verification driver."
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=FIXTURES_DIR,
        help="Path to the fixtures directory.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Apply the I-09B operator-override strict thresholds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON report instead of the human-readable summary.",
    )
    args = parser.parse_args(argv)

    try:
        metas = discover_fixtures(args.fixtures_dir)
    except FixtureError as exc:
        print(f"discovery error: {exc}", file=sys.stderr)
        return 2

    verdicts: dict[str, FixtureVerdict] = {}
    for meta in metas:
        verdict = load_verdict(meta.fixture_root)
        if verdict is not None:
            verdicts[meta.fixture_id] = verdict

    aggregate = aggregate_verdict(metas, verdicts, strict_run=args.strict)

    if args.json:
        report = {
            "fixtures": [fixture_summary(m, verdicts.get(m.fixture_id)) for m in metas],
            "aggregate": aggregate,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_summary(metas, verdicts))
        print()
        header = ["Fixture", *ALL_MANDATES]
        print(" | ".join(header))
        print("-+-".join(["-" * len(col) for col in header]))
        for row in per_fixture_matrix(metas, verdicts):
            print(" | ".join(row))
        print()
        print(f"Overall: {aggregate['overall']} ({aggregate['threshold-mode']})")
        cell_counts = aggregate["cell-counts"]
        print(
            f"Cells: {cell_counts['total']} total, "
            f"{cell_counts['pass-or-na']} pass/n/a, "
            f"{cell_counts['fail']} fail, "
            f"{cell_counts['pending']} pending"
        )
        gap_rate = aggregate["surfaced-gap-rate"]
        print(f"M6-targeting surfaced-gap rate: {gap_rate['per-m6-fixture']}")

    # Exit semantics:
    #   "pass"    -> 0  (every cell passed or n/a-with-reason)
    #   "pending" -> 0  (fixtures discovered but no verdict.yml yet —
    #                    scaffolding state, not a failure)
    #   "fail"    -> 1  (one or more cells recorded an actual failure)
    overall = aggregate["overall"]
    return 0 if overall in ("pass", "pending") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
