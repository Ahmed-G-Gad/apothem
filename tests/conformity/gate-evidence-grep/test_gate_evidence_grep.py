# SPDX-License-Identifier: MIT

"""Behaviour contract for the gate-evidence-grep validator.

The validator walks ``<root>/.apothem/plans/<suite>/`` and flags a gate claim
(a pass verdict on a named gate) in a phase report, the progress file, the
completion report, an attestation file or the handoff manifest when the
command, the exit status or output, and the HEAD sha are not recorded beside
it. It also checks the fields of a ``conformity-attestation`` block. It is
advisory: the CLI exits 0 by default and exits 2 under ``--strict``.

Every fixture is built under ``tmp_path`` so the behaviour is exercised
deterministically, independent of any live plan suite. The report text is
modelled on real phase reports, not on the template placeholders.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.conformity import _grep_base, gate, gate_evidence_grep
from apothem.conformity import gate_evidence_grep as grep

TICK = "\N{WHITE HEAVY CHECK MARK}"
CROSS = "\N{CROSS MARK}"
HEAD = "3f2a9c1"
REPORT = Path("phases") / "02-api" / "REPORT.md"

FULL_TABLE = f"""# Phase 02 - API - Execution Report

**Date:** 2026-10-25 | **Commit(s):** `a1b2c3d`

## Quality Gates (HEAD `{HEAD}`)

| Gate | Command | Exit | Output | Result |
|------|---------|------|--------|--------|
| Lint | `ruff check .` | 0 | All checks passed | {TICK} PASS |
| Types | `python -m mypy` | 0 | Success: no issues found in 41 source files | {TICK} PASS |
| Tests | `python -m pytest -q` | 0 | 412 passed in 31s | {TICK} PASS |

## Exit Criteria

- [x] Quality gates pass
- [ ] Docs updated
"""

ATTESTATION_FIELDS = """  bars:
    M1-host-agnosticism: pass
    M2-editorial-disclosure: n/a (no amendments)
    M3-ten-dimensions: pass
    M4-self-application: pass
    M5-authority: pass
    M6-expertise: pass
    M7-option-annotation: n/a (no option set)
    M8-definitiveness: pass
    M9-visual-leverage: n/a (subject not structural)
    M10-bidirectional-binding: pass
    M11-agile-sprints: n/a (trivial work)
    M12-phase-layout: pass
    M13-code-craft: pass
    M14-systemicity: pass
    M15-production-ready: pass
  surfaced-gaps: []
  unresolved-inquiries: []
  amendments-disclosed: []
"""


def _attestation(
    *,
    ecosystem: str = "8f3e2d1c4b5a",
    date: str | None = "2026-10-25",
    fields: str = ATTESTATION_FIELDS,
) -> str:
    """Render a ``conformity-attestation`` YAML block."""
    lines = ["conformity-attestation:", "  artifact: phases/02-api/REPORT.md"]
    if ecosystem:
        lines.append(f"  ecosystem-version: {ecosystem}")
    body = "\n".join(lines) + "\n" + fields
    return body + (f"  date: {date}\n" if date else "")


def _fenced_attestation(*, lead: str = "", **kwargs: str | None) -> str:
    """Render a report section holding an attestation block in a YAML fence."""
    intro = f"{lead}\n\n" if lead else ""
    return (
        "# Phase 02 - Report\n\n## Gate attestation\n\n"
        f"{intro}```yaml\n{_attestation(**kwargs)}```\n"  # type: ignore[arg-type]
    )


def _suite(root: Path, files: dict[str | Path, str], name: str = "demo") -> Path:
    """Write ``files`` under ``<root>/.apothem/plans/<name>/``; return the suite."""
    suite = root / ".apothem" / "plans" / name
    for rel, body in files.items():
        target = suite / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return suite


def _report(root: Path, body: str) -> grep.GrepResult:
    """Check a suite whose only file is the phase report ``body``."""
    _suite(root, {REPORT: body})
    return grep.check(root)


def _missing(result: grep.GrepResult) -> list[list[str]]:
    return [f.missing for f in result.findings]


# ---------------------------------------------------------------------------
# Gate claims: what counts as evidence
# ---------------------------------------------------------------------------


def test_full_evidence_table_passes(tmp_path: Path) -> None:
    """A row with command, exit, output columns and a heading sha is clean."""
    result = _report(tmp_path, FULL_TABLE)
    assert result.passed is True
    assert result.findings == []
    assert result.claims_inspected == 4  # three rows and the ticked roll-up
    assert result.files_inspected == 1
    assert result.suites_inspected == 1


def test_bare_verdict_rows_are_flagged(tmp_path: Path) -> None:
    """A pass verdict with no command, output or sha is flagged on all three."""
    body = f"""# Phase 02 - Report

## Verification Results

| ID | Check | Result | Notes |
|----|-------|--------|-------|
| V1 | Lint clean | {TICK} PASS | ruff |
| V2 | Config file exists | {TICK} PASS | |
| V3 | Test suite | {TICK} PASS | all tests pass |
"""
    result = _report(tmp_path, body)
    assert result.passed is False
    rows = body.splitlines()
    flagged = [i + 1 for i, ln in enumerate(rows) if ln.startswith(("| V1", "| V3"))]
    assert [f.line for f in result.findings] == flagged  # V2 names no gate
    assert _missing(result) == [["command", "output", "sha"]] * 2
    finding = result.findings[0]
    assert finding.surface == ".apothem/plans/demo/phases/02-api/REPORT.md"
    assert finding.suite == "demo"
    assert finding.kind == "gate-claim"
    assert finding.form == "row"
    assert "Lint clean" in finding.claim


@pytest.mark.parametrize(
    ("line", "missing"),
    [
        pytest.param(
            f"Ran `ruff check .` at {HEAD}: lint PASS.", ["output"], id="no-output"
        ),
        pytest.param(f"Lint PASS at {HEAD}, exit 0.", ["command"], id="no-command"),
        pytest.param("Ran `ruff check .`, exit 0: lint PASS.", ["sha"], id="no-sha"),
        pytest.param("The lint gate passed.", ["command", "output", "sha"], id="none"),
        pytest.param(
            f"Ran `ruff check .` at {HEAD}, exit 0: lint PASS.", [], id="full"
        ),
    ],
)
def test_paragraph_reports_exactly_the_missing_items(
    tmp_path: Path, line: str, missing: list[str]
) -> None:
    """Each absent item is named; a paragraph holding all three is clean."""
    result = _report(tmp_path, f"# Report\n\n## Gates\n\n{line}\n")
    assert _missing(result) == ([missing] if missing else [])


@pytest.mark.parametrize(
    "exit_text",
    [
        "exit 0",
        "exit code: 0",
        "exit=0",
        "exited with status 0",
        "rc=0",
        "exit status 1",
        "returncode: 0",
    ],
)
def test_exit_status_forms_count_as_output(tmp_path: Path, exit_text: str) -> None:
    line = f"Ran `ruff check .` at {HEAD}, {exit_text}: lint PASS."
    assert _report(tmp_path, f"# R\n\n## G\n\n{line}\n").passed is True


@pytest.mark.parametrize(
    "output_text",
    [
        "412 passed in 31s",
        "output: ci/logs/lint-4821.txt",
        "see `build/ruff.log`",
        "https://ci.example.com/acme/app/actions/runs/88231",
        "Success: no issues found in 41 source files",
    ],
)
def test_summary_line_and_pointer_forms_count_as_output(
    tmp_path: Path, output_text: str
) -> None:
    line = f"Ran `pytest -q` at {HEAD} ({output_text}): tests PASS."
    assert _report(tmp_path, f"# R\n\n## G\n\n{line}\n").passed is True


def test_verdict_word_alone_is_not_output(tmp_path: Path) -> None:
    """``clean`` and ``ok`` restate the verdict; they are not a result."""
    line = f"Ran `ruff check .` at {HEAD}: lint clean, all OK."
    result = _report(tmp_path, f"# R\n\n## G\n\n{line}\n")
    assert _missing(result) == [["output"]]


def test_pasted_output_block_beside_the_claim_counts(tmp_path: Path) -> None:
    """A fenced block of command and output under a claim is its evidence."""
    body = f"""# R

## Gates

Lint PASS at HEAD {HEAD}.

```text
$ ruff check .
All checks passed!
```
"""
    assert _report(tmp_path, body).passed is True


def test_pasted_command_alone_is_not_output(tmp_path: Path) -> None:
    body = f"""# R

## Gates

Lint PASS at HEAD {HEAD}.

```text
$ ruff check .
```
"""
    assert _missing(_report(tmp_path, body)) == [["output"]]


def test_report_header_commit_is_not_the_gate_sha(tmp_path: Path) -> None:
    """``Commit(s):`` names the phase's commits, not HEAD when the gate ran."""
    body = f"""# Phase 02 - Report

**Date:** 2026-10-25 | **Commit(s):** `{HEAD}`

## Gates

Ran `pytest -q`, exit 0, 412 passed: tests PASS.
"""
    assert _missing(_report(tmp_path, body)) == [["sha"]]


def test_all_digit_sha_needs_a_label(tmp_path: Path) -> None:
    labelled = "Ran `pytest -q` at HEAD 1234567, exit 0: tests PASS."
    bare = "Ran `pytest -q` at 1234567, exit 0: tests PASS."
    assert _report(tmp_path, f"# R\n\n## G\n\n{labelled}\n").passed is True
    other = tmp_path / "other"
    other.mkdir()
    assert _missing(_report(other, f"# R\n\n## G\n\n{bare}\n")) == [["sha"]]


def test_placeholder_values_are_not_evidence(tmp_path: Path) -> None:
    body = """# R

## Gates

- Lint PASS
  - Command: TBD
  - Output: <paste output>
  - HEAD: [hash]
"""
    result = _report(tmp_path, body)
    assert _missing(result) == [["command", "output", "sha"]]


def test_neutral_lead_in_paragraph_covers_the_rows_below(tmp_path: Path) -> None:
    """One recorded run (command, exit, HEAD) can back a table of results."""
    body = f"""# R

## Gate results

All checks ran through `make check` at HEAD {HEAD}; it exited 0.

| Gate | Result |
|------|--------|
| Lint | {TICK} PASS |
| Tests | {TICK} PASS |
"""
    assert _report(tmp_path, body).passed is True


def test_claim_paragraph_is_not_context_for_the_next_claim(tmp_path: Path) -> None:
    """Evidence for one gate does not stand behind a different gate's claim."""
    body = f"""# R

## Gates

Ran `pytest -q` at {HEAD}: exit 0, 412 passed.

The lint gate passed after fixing two imports.
"""
    result = _report(tmp_path, body)
    assert len(result.findings) == 1
    assert "lint gate" in result.findings[0].claim
    assert result.findings[0].missing == ["command", "output", "sha"]


def test_sha_in_heading_applies_only_below_it(tmp_path: Path) -> None:
    body = f"""# R

## Gates at HEAD {HEAD}

Ran `pytest -q`, exit 0: tests PASS.

## Later

Ran `pytest -q`, exit 0: tests PASS.
"""
    result = _report(tmp_path, body)
    rows = body.splitlines()
    last_run = max(i for i, ln in enumerate(rows) if ln.startswith("Ran")) + 1
    assert [f.line for f in result.findings] == [last_run]
    assert _missing(result) == [["sha"]]


# ---------------------------------------------------------------------------
# Gate claims: what is not a claim
# ---------------------------------------------------------------------------


def test_phase_status_rows_are_not_gate_claims(tmp_path: Path) -> None:
    """A check mark beside ``Complete`` is a phase status, even for a gate phase."""
    body = f"""# PROGRESS

## Phase Tracker

| # | Phase | Status | Report | Commit |
|---|-------|--------|--------|--------|
| 01 | Lint configuration | {TICK} Complete | phases/01-lint/REPORT.md | `abc1234` |
| 02 | Test suite build | {TICK} Complete | phases/02-api/REPORT.md | `def5678` |

## Phase Output Registry

| Phase | Declared Output | Actual Path | Verified |
|-------|-----------------|-------------|----------|
| 01 | `tests/unit/test_lint.py` | `tests/unit/test_lint.py` | {TICK} |
"""
    _suite(tmp_path, {"PROGRESS.md": body})
    result = grep.check(tmp_path)
    assert result.passed is True
    assert result.claims_inspected == 0
    assert result.files_inspected == 1


def test_failures_directives_and_unticked_boxes_are_not_claims(
    tmp_path: Path,
) -> None:
    body = f"""# R

## Gates

- Lint {CROSS} FAIL, 3 errors remain
- Tests failed: 2 failed, 410 passed
- Lint must pass before merge
- [ ] Tests pass
- Build is not passing yet
- Phase summary: 12 PASS, 0 FAIL
"""
    result = _report(tmp_path, body)
    assert result.passed is True
    assert result.claims_inspected == 0


def test_gate_names_inside_paths_are_not_gates(tmp_path: Path) -> None:
    body = """# R

## Outputs

- Wrote tests/unit/test_lint.py and `src/build/lint.py`: PASS
- See [the report](phases/01-lint/REPORT.md): PASS
"""
    assert _report(tmp_path, body).claims_inspected == 0


# ---------------------------------------------------------------------------
# Roll-ups, nesting and headings
# ---------------------------------------------------------------------------


def test_ticked_rollup_is_supported_by_a_complete_record(tmp_path: Path) -> None:
    result = _report(tmp_path, FULL_TABLE)
    assert result.passed is True


def test_ticked_rollup_without_any_record_is_flagged(tmp_path: Path) -> None:
    body = "# R\n\n## Exit Criteria\n\n- [x] Quality gates pass\n- [x] Lint and tests pass\n"
    result = _report(tmp_path, body)
    assert [f.kind for f in result.findings] == ["rollup-claim", "rollup-claim"]
    assert _missing(result) == [["command", "output", "sha"]] * 2


def test_general_gates_statement_is_a_rollup(tmp_path: Path) -> None:
    body = f"""# R

## Result

All gates green {TICK}

## Gates at HEAD {HEAD}

Ran `ruff check .`, exit 0: lint PASS.
"""
    result = _report(tmp_path, body)
    assert result.passed is True  # the second section is a complete record


def test_nested_list_is_judged_child_by_child(tmp_path: Path) -> None:
    body = f"""# R

## Gates

- Quality gates (HEAD `{HEAD}`):
  - lint: `ruff check .`, exit 0, PASS
  - tests: `pytest -q`, exit 0, 412 passed, PASS
  - types: PASS
"""
    result = _report(tmp_path, body)
    assert len(result.findings) == 1
    assert "types" in result.findings[0].claim
    assert result.findings[0].missing == ["command", "output"]


def test_single_gate_item_with_child_lines_is_one_claim(tmp_path: Path) -> None:
    body = f"""# R

## Gates

- Lint gate
  - Result: PASS
  - Command: `ruff check .`
  - Exit: 0 (All checks passed!)
  - HEAD: `{HEAD}`
"""
    result = _report(tmp_path, body)
    assert result.passed is True
    assert result.claims_inspected == 1


def test_heading_claim_reads_its_section_body(tmp_path: Path) -> None:
    good = f"""# R

### Lint {TICK} PASS

Command: `ruff check .`
Exit: 0
HEAD: {HEAD}
"""
    bare = f"""# R

### Lint {TICK} PASS

### Tests

Nothing to report.
"""
    assert _report(tmp_path, good).passed is True
    other = tmp_path / "other"
    other.mkdir()
    result = _report(other, bare)
    assert [f.form for f in result.findings] == ["heading"]
    assert result.findings[0].missing == ["command", "output", "sha"]


def test_aggregate_heading_does_not_swallow_its_rows(tmp_path: Path) -> None:
    """A heading that only says "gates pass" leaves each row its own claim."""
    body = f"""# R

## Quality Gates at HEAD {HEAD} {TICK}

| Gate | Command | Exit | Result |
|------|---------|------|--------|
| Lint | `ruff check .` | 0 | PASS |
| Tests | | | PASS |
"""
    result = _report(tmp_path, body)
    assert [f.form for f in result.findings] == ["row"]
    assert "Tests" in result.findings[0].claim
    assert result.findings[0].missing == ["command", "output"]


def test_yaml_gate_records_are_judged_record_by_record(tmp_path: Path) -> None:
    body = f"""# R

## Gate records

```yaml
gates:
  - gate: lint
    status: pass
    command: ruff check .
    exit: 0
    head: {HEAD}
  - gate: tests
    status: pass
    command: pytest -q
```
"""
    result = _report(tmp_path, body)
    assert len(result.findings) == 1
    assert result.findings[0].form == "record"
    assert "tests" in result.findings[0].claim
    assert result.findings[0].missing == ["output", "sha"]


def test_sibling_evidence_keys_back_every_claim_key(tmp_path: Path) -> None:
    """``command``, ``exit`` and ``head`` written beside the claim keys count."""
    manifest = f"""gate-attestation:
  lint: pass
  types: pass
  tests: pass
  head: {HEAD}
  command: make check
  exit: 0
"""
    _suite(tmp_path, {Path("_inputs") / "handoff-manifest.yml": manifest})
    result = grep.check(tmp_path)
    assert result.findings == []
    assert result.claims_inspected == 3


def test_sibling_keys_with_a_gap_name_exactly_that_gap(tmp_path: Path) -> None:
    manifest = f"""gate-attestation:
  lint: pass
  types: pass
  tests: pass
  head: {HEAD}
  command: make check
"""
    _suite(tmp_path, {Path("_inputs") / "handoff-manifest.yml": manifest})
    result = grep.check(tmp_path)
    assert _missing(result) == [["output"]] * 3


def test_claim_keys_alone_still_lack_all_three_items(tmp_path: Path) -> None:
    manifest = "gate-attestation:\n  lint: pass\n  types: pass\n  tests: pass\n"
    _suite(tmp_path, {Path("_inputs") / "handoff-manifest.yml": manifest})
    assert _missing(grep.check(tmp_path)) == [["command", "output", "sha"]] * 3


def test_run_bullet_above_claim_bullets_is_their_evidence(tmp_path: Path) -> None:
    """A "Run:" bullet is context for the claim bullets that follow it."""
    body = f"""# R

## Gates

- Run: `make check`, exit 0, HEAD {HEAD}
- Lint: pass
- Tests: pass
"""
    result = _report(tmp_path, body)
    assert result.findings == []
    assert result.claims_inspected == 2


def test_run_paragraph_above_claim_bullets_is_their_evidence(tmp_path: Path) -> None:
    body = f"""# R

## Gates

Run: `make check`, exit 0, HEAD {HEAD}

- Lint: pass
- Tests: pass
"""
    assert _report(tmp_path, body).findings == []


def test_bullet_evidence_does_not_cross_into_another_section(tmp_path: Path) -> None:
    body = f"""# R

## Earlier

- Run: `make check`, exit 0, HEAD {HEAD}

## Gates

- Lint: pass
"""
    assert _missing(_report(tmp_path, body)) == [["command", "output", "sha"]]


def test_table_row_columns_supply_evidence(tmp_path: Path) -> None:
    body = f"""# R

## Gates

| Gate | Command | Exit code | Head | Result |
|------|---------|-----------|------|--------|
| Lint | `ruff check .` | 0 | {HEAD} | PASS |
| Tests | `pytest -q` | | {HEAD} | PASS |
"""
    result = _report(tmp_path, body)
    assert len(result.findings) == 1
    assert "Tests" in result.findings[0].claim
    assert result.findings[0].missing == ["output"]


# ---------------------------------------------------------------------------
# Attestation blocks
# ---------------------------------------------------------------------------

RUN_RECORD = (
    f"Ran `python -m apothem.conformity.gate --all --strict .` at HEAD {HEAD}: "
    "exit 0, 54 passed."
)


def test_complete_attestation_with_run_record_passes(tmp_path: Path) -> None:
    result = _report(tmp_path, _fenced_attestation(lead=RUN_RECORD))
    assert result.passed is True
    assert result.claims_inspected == 0  # the block is judged by its schema


def test_conformant_attestation_needs_no_run_record(tmp_path: Path) -> None:
    """The rule's schema has no command, exit or SHA field, so none is demanded."""
    result = _report(tmp_path, _fenced_attestation())
    assert result.findings == []
    assert result.passed is True


def test_conformant_attestation_file_has_no_findings(tmp_path: Path) -> None:
    """A schema-conformant ``attestation.yml`` is not read as a prose gate claim."""
    _suite(tmp_path, {Path("_outputs") / "02-api" / "attestation.yml": _attestation()})
    result = grep.check(tmp_path)
    assert result.findings == []
    assert result.files_inspected == 1


def test_ecosystem_version_is_not_the_head_sha(tmp_path: Path) -> None:
    """``ecosystem-version`` names the rule set in force, not the project HEAD."""
    body = (
        "# R\n\n## Gates\n\n"
        "Ran `python -m pytest -q`, exit 0, 54 passed: tests PASS.\n"
        "ecosystem-version: 8f3e2d1c4b5a\n"
    )
    assert _missing(_report(tmp_path, body)) == [["sha"]]


@pytest.mark.parametrize(
    ("kwargs", "gap"),
    [
        pytest.param({"date": None}, "date (absent or unfilled)", id="no-date"),
        pytest.param({"date": "25/10/2026"}, "date (not ISO-8601)", id="bad-date"),
        pytest.param(
            {"ecosystem": ""}, "ecosystem-version (absent or unfilled)", id="no-eco"
        ),
        pytest.param(
            {"ecosystem": "<sha>"},
            "ecosystem-version (absent or unfilled)",
            id="placeholder-eco",
        ),
    ],
)
def test_attestation_missing_a_required_field(
    tmp_path: Path, kwargs: dict[str, str | None], gap: str
) -> None:
    result = _report(tmp_path, _fenced_attestation(lead=RUN_RECORD, **kwargs))
    findings = [f for f in result.findings if f.kind == "attestation-incomplete"]
    assert len(findings) == 1
    assert findings[0].missing == [gap]
    assert "rules/pre-emission-gate-bars.md" in findings[0].detail


def test_attestation_n_a_needs_a_reason(tmp_path: Path) -> None:
    fields = ATTESTATION_FIELDS.replace("n/a (no amendments)", "n/a")
    body = _fenced_attestation(lead=RUN_RECORD, fields=fields)
    result = _report(tmp_path, body)
    findings = [f for f in result.findings if f.kind == "attestation-incomplete"]
    assert [f.missing for f in findings] == [["n/a without a reason"]]


def test_attestation_missing_arrays_and_bars(tmp_path: Path) -> None:
    fields = (
        "  bars:\n    M1-host-agnosticism: pass\n    M15-production-ready: n/a (x)\n"
    )
    result = _report(tmp_path, _fenced_attestation(lead=RUN_RECORD, fields=fields))
    findings = [f for f in result.findings if f.kind == "attestation-incomplete"]
    assert len(findings) == 1
    gaps = findings[0].missing
    assert "surfaced-gaps (array not written out)" in gaps
    assert "unresolved-inquiries (array not written out)" in gaps
    assert "amendments-disclosed (array not written out)" in gaps
    assert gaps[-1] == "bar lines " + ", ".join(f"M{n}" for n in range(2, 15))


def test_all_n_a_attestation_claims_no_pass(tmp_path: Path) -> None:
    fields = ATTESTATION_FIELDS
    for word in ("pass", "pass\n"):
        fields = fields.replace(f": {word}", ": n/a (not applicable)")
    result = _report(tmp_path, _fenced_attestation(fields=fields))
    assert result.passed is True


def test_unclosed_yaml_fence_still_checks_the_attestation(tmp_path: Path) -> None:
    body = """# R

## Gate attestation

```yaml
conformity-attestation:
  artifact: x
"""
    result = _report(tmp_path, body)
    assert [f.kind for f in result.findings] == ["attestation-incomplete"]


def test_attestation_file_is_inspected(tmp_path: Path) -> None:
    body = _attestation(date=None)
    _suite(tmp_path, {Path("_outputs") / "02-api" / "attestation.yml": body})
    result = grep.check(tmp_path)
    kinds = sorted(f.kind for f in result.findings)
    assert kinds == ["attestation-incomplete"]
    assert result.findings[0].surface.endswith("_outputs/02-api/attestation.yml")


@pytest.mark.parametrize(
    ("replacement", "flagged"),
    [
        pytest.param("n/a", True, id="bare"),
        pytest.param("N/A", True, id="upper-case"),
        pytest.param('"n/a"', True, id="double-quoted"),
        pytest.param("'n/a'", True, id="single-quoted"),
        pytest.param("n/a #", True, id="empty-comment"),
        pytest.param("n/a # not code", False, id="comment-reason"),
        pytest.param('"n/a" # not code', False, id="quoted-with-comment-reason"),
        pytest.param("n/a (not code)", False, id="parenthesised-reason"),
        pytest.param("n/a: not code", False, id="colon-reason"),
    ],
)
def test_attestation_n_a_forms(tmp_path: Path, replacement: str, flagged: bool) -> None:
    """A quoted ``n/a`` is still bare; a comment or parenthesis is a reason."""
    fields = ATTESTATION_FIELDS.replace("n/a (no amendments)", replacement)
    result = _report(tmp_path, _fenced_attestation(fields=fields))
    gaps = [g for f in result.findings for g in f.missing]
    assert ("n/a without a reason" in gaps) is flagged


def test_manifest_gate_block_is_inspected(tmp_path: Path) -> None:
    manifest = "design_gate:\n  validation: pass\n  bars_passed: 15\n"
    _suite(tmp_path, {Path("_inputs") / "handoff-manifest.yml": manifest})
    result = grep.check(tmp_path)
    assert [f.kind for f in result.findings] == ["rollup-claim"]


# ---------------------------------------------------------------------------
# Scope, roots and reporting
# ---------------------------------------------------------------------------


def test_only_report_progress_completion_and_attestation_files_are_read(
    tmp_path: Path,
) -> None:
    claim = "Lint PASS and tests PASS.\n"
    _suite(
        tmp_path,
        {
            "PHASE.md": claim,
            "MASTER-PLAN.md": claim,
            "PLAN-NOTES.md": claim,
            "_spec/spec.md": claim,
            "phases/01-x/REPORT.md": claim,
            "PROGRESS.md": claim,
            "COMPLETION.md": claim,
        },
    )
    result = grep.check(tmp_path)
    surfaces = sorted({f.surface for f in result.findings})
    assert surfaces == [
        ".apothem/plans/demo/COMPLETION.md",
        ".apothem/plans/demo/PROGRESS.md",
        ".apothem/plans/demo/phases/01-x/REPORT.md",
    ]
    assert result.files_inspected == 3


def test_mirror_report_under_outputs_is_inspected(tmp_path: Path) -> None:
    _suite(tmp_path, {Path("_outputs") / "02-api" / "REPORT.md": "Lint PASS.\n"})
    assert len(grep.check(tmp_path).findings) == 1


def test_no_plans_tree_is_an_empty_scope(tmp_path: Path) -> None:
    result = grep.check(tmp_path)
    assert result.passed is True
    assert (result.suites_inspected, result.files_inspected) == (0, 0)


def test_every_suite_is_walked(tmp_path: Path) -> None:
    _suite(tmp_path, {REPORT: FULL_TABLE}, name="alpha")
    _suite(tmp_path, {REPORT: "Lint PASS.\n"}, name="beta")
    result = grep.check(tmp_path)
    assert result.suites_inspected == 2
    assert {f.suite for f in result.findings} == {"beta"}


def test_root_may_be_the_plans_directory_or_one_suite(tmp_path: Path) -> None:
    suite = _suite(tmp_path, {REPORT: "Lint PASS.\n"})
    for root in (suite.parent, suite):
        result = grep.check(root)
        assert len(result.findings) == 1, root
        assert result.files_inspected == 1


def test_unreadable_file_is_a_note_not_a_finding(tmp_path: Path) -> None:
    suite = _suite(tmp_path, {"PROGRESS.md": "# P\n"})
    (suite / "COMPLETION.md").write_bytes(b"\xff\xfe\x00bad")
    result = grep.check(tmp_path)
    assert result.passed is True
    assert result.files_inspected == 1
    assert len(result.notes) == 1
    assert "COMPLETION.md" in result.notes[0]


def test_crlf_reports_are_read_like_lf(tmp_path: Path) -> None:
    suite = _suite(tmp_path, {})
    path = suite / REPORT
    path.parent.mkdir(parents=True)
    path.write_bytes(FULL_TABLE.replace("\n", "\r\n").encode("utf-8"))
    assert grep.check(tmp_path).passed is True


def test_json_report_shape(tmp_path: Path) -> None:
    result = _report(tmp_path, "# R\n\n## G\n\nLint PASS.\n")
    payload = json.loads(result.to_json())
    assert payload["grep"] == "gate-evidence-grep"
    assert payload["advisory"] is True
    assert payload["passed"] is False
    assert set(payload) == {
        "grep",
        "root",
        "suites_inspected",
        "files_inspected",
        "claims_inspected",
        "passed",
        "advisory",
        "findings",
        "notes",
    }
    assert set(payload["findings"][0]) == {
        "surface",
        "suite",
        "line",
        "kind",
        "form",
        "claim",
        "missing",
        "detail",
        "rule",
    }
    assert "commands/plan-execute.md" in payload["findings"][0]["rule"]


# ---------------------------------------------------------------------------
# Command line and gate registration
# ---------------------------------------------------------------------------


def test_cli_is_advisory_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _suite(tmp_path, {REPORT: "Lint PASS.\n"})
    code = gate_evidence_grep._main(["gate-evidence-grep", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == _grep_base.EXIT_PASS
    assert payload["passed"] is False
    assert payload["advisory"] is True
    assert payload["inspected"] == 1


def test_cli_strict_exits_two_on_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _suite(tmp_path, {REPORT: "Lint PASS.\n"})
    code = gate_evidence_grep._main(["gate-evidence-grep", str(tmp_path), "--strict"])
    capsys.readouterr()
    assert code == _grep_base.EXIT_FAIL


def test_cli_strict_passes_a_clean_suite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _suite(tmp_path, {REPORT: FULL_TABLE})
    code = gate_evidence_grep._main(["gate-evidence-grep", str(tmp_path), "--strict"])
    capsys.readouterr()
    assert code == _grep_base.EXIT_PASS


def test_cli_declares_an_empty_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A checkout with no plan suite passes and says the empty scope is expected."""
    code = gate_evidence_grep._main(["gate-evidence-grep", str(tmp_path), "--strict"])
    payload = json.loads(capsys.readouterr().out)
    assert code == _grep_base.EXIT_PASS
    assert payload["passed"] is True
    assert payload["inspected"] == 0
    assert payload["empty_scope_expected"] is True


def test_validator_is_registered_with_the_gate() -> None:
    assert "gate-evidence-grep" in gate.STANDALONE_MODULES
    assert gate._resolve_validator("gate-evidence-grep") == ("gate-evidence-grep", True)


def test_gate_runs_the_validator_and_reads_its_advisory_verdict(
    tmp_path: Path,
) -> None:
    _suite(tmp_path, {REPORT: "Lint PASS.\n"})
    passed, output = gate._run_standalone("gate-evidence-grep", tmp_path)
    assert passed is True  # advisory: findings never fail the subprocess
    verdict = gate._advisory_verdict(output)
    assert verdict is not None
    assert verdict["passed"] is False
    assert len(verdict["findings"]) == 1  # type: ignore[arg-type]
